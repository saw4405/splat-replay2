"""ゲームプレイ全体を自動処理するユースケース。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List

import cv2

from splat_replay.application.interfaces import (
    VideoRecorder,
    FrameAnalyzerPort,
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
        analyzer: FrameAnalyzerPort,
        transcriber: SpeechTranscriberPort,
        editor: VideoEditorPort,
        uploader: UploadPort,
        extractor: MetadataExtractorPort,
        power: PowerPort,
        metadata_repo: MetadataRepository,
        state_machine: StateMachine,
        obs_settings: OBSSettings,
    ) -> None:
        self.recorder = recorder
        self.analyzer = analyzer
        self.transcriber = transcriber
        self.editor = editor
        self.uploader = uploader
        self.extractor = extractor
        self.power = power
        self.repo = metadata_repo
        self.sm = state_machine
        self.settings = obs_settings
        self.pending: List[Path] = []
        self.logger = get_logger()
        self.rate: int | None = None
        self.result: str | None = None
        self._matching = False
        self._battle_started_at = 0.0

    def _reset(self) -> None:
        """保持している一時情報をリセットする。"""
        self.rate = None
        self.result = None
        self._matching = False
        self._battle_started_at = 0.0

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

    def _update_power_off_count(
        self, frame, off_count: int, last_check: float
    ) -> tuple[int, float, bool]:
        """フレームから電源OFF判定を行い、カウント・時刻・確定判定を返す。"""
        now = time.time()
        detected = False
        if now - last_check >= 10:
            last_check = now
            if self.analyzer.detect_power_off(frame):
                off_count += 1
                self.logger.info("電源 OFF を検出", count=off_count)
            else:
                off_count = 0
            if off_count >= 6:
                detected = True
        return off_count, last_check, detected

    def execute(self) -> None:
        """電源 OFF を監視しつつ自動録画を繰り返す。"""
        self.logger.info("デーモン開始")

        cap = cv2.VideoCapture(self.settings.capture_device_index)
        if not cap.isOpened():
            self.logger.error(
                "キャプチャデバイスを開けません",
                index=self.settings.capture_device_index,
            )
            raise RuntimeError("キャプチャデバイスの取得に失敗しました")

        off_count = 0
        last_check = 0.0
        try:
            while True:
                success, frame = cap.read()
                if not success:
                    self.logger.warning("フレーム取得に失敗しました")
                    time.sleep(1)
                    continue

                off_count, last_check, power_off_detected = (
                    self._update_power_off_count(frame, off_count, last_check)
                )
                if power_off_detected:
                    if self.sm.state in {State.RECORDING, State.PAUSED}:
                        video = self.recorder.stop()
                        audio = self.transcriber.stop_capture()
                        _ = self.transcriber.transcribe(audio)
                        self.pending.append(video)
                        self.sm.handle(Event.POSTGAME_DETECTED)
                    self._process_pending()
                    break

                if self.sm.state is State.STANDBY:
                    if self.analyzer.detect_match_select(frame):
                        rate = self.analyzer.extract_rate(frame)
                        if rate is not None:
                            self.rate = rate
                            self.logger.info("レート取得", rate=rate)
                    if self.analyzer.detect_schedule_change(frame):
                        self.logger.info(
                            "スケジュール変更を検出、情報をリセット"
                        )
                        self._reset()
                        continue
                    if (
                        not self._matching
                        and self.analyzer.detect_matching_start(frame)
                    ):
                        self._matching = True
                        continue
                    if self._matching and self.analyzer.detect_battle_start(
                        frame
                    ):
                        self.recorder.start()
                        self.transcriber.start_capture()
                        self._battle_started_at = time.time()
                        self.sm.handle(Event.BATTLE_STARTED)
                        self._matching = False

                elif self.sm.state is State.RECORDING:
                    now = time.time()
                    if (
                        now - self._battle_started_at <= 60
                        and self.analyzer.detect_battle_abort(frame)
                    ):
                        self.logger.info("バトル中断を検出")
                        self.recorder.stop()
                        self.transcriber.stop_capture()
                        self.sm.handle(Event.EARLY_ABORT)
                        self._reset()
                        continue
                    if now - self._battle_started_at >= 600:
                        video = self.recorder.stop()
                        audio = self.transcriber.stop_capture()
                        _ = self.transcriber.transcribe(audio)
                        self.pending.append(video)
                        self.sm.handle(Event.POSTGAME_DETECTED)
                        self._reset()
                        continue
                    if self.analyzer.detect_loading(
                        frame
                    ) or self.analyzer.detect_finish(frame):
                        self.recorder.pause()
                        self.transcriber.stop_capture()
                        self.sm.handle(Event.LOADING_DETECTED)
                        continue
                    jud = self.analyzer.detect_judgement(frame)
                    if jud is not None:
                        self.result = jud
                    if self.analyzer.detect_result(frame):
                        video = self.recorder.stop()
                        audio = self.transcriber.stop_capture()
                        _ = self.transcriber.transcribe(audio)
                        self.pending.append(video)
                        self.sm.handle(Event.POSTGAME_DETECTED)
                        self._reset()

                elif self.sm.state is State.PAUSED:
                    if self.analyzer.detect_loading_end(
                        frame
                    ) or self.analyzer.detect_finish_end(frame):
                        self.recorder.resume()
                        self.transcriber.start_capture()
                        self.sm.handle(Event.LOADING_FINISHED)
        finally:
            cap.release()
