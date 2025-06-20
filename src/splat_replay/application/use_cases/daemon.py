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
        while True:
            frame = Path()

            if self.analyzer.detect_power_off():
                # 途中状態でも録画を終了して処理を進める
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
