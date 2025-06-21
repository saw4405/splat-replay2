"""ゲームプレイ全体を自動処理するユースケース。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List

from splat_replay.application.interfaces import (
    VideoRecorder,
    ScreenAnalyzerPort,
    SpeechTranscriberPort,
    VideoEditorPort,
    UploadPort,
    MetadataExtractorPort,
    PowerPort,
)
from splat_replay.domain.repositories.metadata_repo import MetadataRepository
from splat_replay.domain.services.state_machine import (
    Event,
    State,
    StateMachine,
)
from splat_replay.shared.logger import get_logger
from splat_replay.shared.config import OBSSettings


class DaemonUseCase:
    """ユーザー操作なしで録画からアップロードまでを制御する。"""

    def __init__(
        self,
        recorder: VideoRecorder,
        analyzer: ScreenAnalyzerPort,
        transcriber: SpeechTranscriberPort,
        editor: VideoEditorPort,
        uploader: UploadPort,
        extractor: MetadataExtractorPort,
        power: PowerPort,
        repo: MetadataRepository,
        state_machine: StateMachine,
        settings: OBSSettings,
    ) -> None:
        self.recorder = recorder
        self.analyzer = analyzer
        self.transcriber = transcriber
        self.editor = editor
        self.uploader = uploader
        self.extractor = extractor
        self.power = power
        self.repo = repo
        self.sm = state_machine
        self.settings = settings
        self.pending: List[Path] = []
        self.logger = get_logger()

    def _process_pending(self) -> None:
        """溜まっている録画を編集しアップロードする。"""
        for clip in list(self.pending):
            edited = self.editor.process(clip)
            match = self.extractor.extract_from_video(edited)
            self.repo.save(match)
            video_id = self.uploader.upload(edited)
            _ = video_id
            self.pending.remove(clip)
        self.power.sleep()

    def execute(self) -> None:
        """電源 OFF を監視しつつ自動録画を繰り返す。"""
        self.logger.info("デーモン開始")
        import cv2

        cap = cv2.VideoCapture(self.settings.capture_device_index)
        if not cap.isOpened():
            self.logger.error(
                "キャプチャデバイスを開けません",
                index=self.settings.capture_device_index,
            )
            raise RuntimeError("キャプチャデバイスの取得に失敗しました")

        try:
            # 電源OFF検出の連続回数
            off_count = 0
            # 最後に電源OFFを確認した時刻
            last_check = 0.0
            while True:
                success, frame = cap.read()
                if not success:
                    self.logger.warning("フレーム取得に失敗しました")
                    time.sleep(1)
                    continue

                now = time.time()
                # 約10秒に1回だけ電源OFFを確認する
                if now - last_check >= 10:
                    last_check = now
                    if self.analyzer.detect_power_off(frame):
                        off_count += 1
                    else:
                        off_count = 0

                    # 6回連続でOFFを検出したら確定とみなす
                    if off_count >= 6:
                        if self.sm.state in {State.RECORDING, State.PAUSED}:
                            video = self.recorder.stop()
                            audio = self.transcriber.stop_capture()
                            _ = self.transcriber.transcribe(audio)
                            self.pending.append(video)
                            self.sm.handle(Event.POSTGAME_DETECTED)
                        self._process_pending()
                        break

                if (
                    self.sm.state is State.STANDBY
                    and self.analyzer.detect_battle_start(frame)
                ):
                    self.recorder.start()
                    self.transcriber.start_capture()
                    self.sm.handle(Event.BATTLE_STARTED)

                elif (
                    self.sm.state is State.RECORDING
                    and self.analyzer.detect_loading(frame)
                ):
                    self.recorder.pause()
                    self.transcriber.stop_capture()
                    self.sm.handle(Event.LOADING_DETECTED)

                elif (
                    self.sm.state is State.PAUSED
                    and self.analyzer.detect_loading_end(frame)
                ):
                    self.recorder.resume()
                    self.transcriber.start_capture()
                    self.sm.handle(Event.LOADING_FINISHED)

                elif (
                    self.sm.state is State.RECORDING
                    and self.analyzer.detect_result(frame)
                ):
                    video = self.recorder.stop()
                    audio = self.transcriber.stop_capture()
                    _ = self.transcriber.transcribe(audio)
                    self.pending.append(video)
                    self.sm.handle(Event.POSTGAME_DETECTED)

                time.sleep(1)
        finally:
            cap.release()
