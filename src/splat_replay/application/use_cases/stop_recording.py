"""録画を終了するユースケース。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import VideoRecorder
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.shared.logger import get_logger


class StopRecordingUseCase:
    """録画を停止してファイルを取得する。"""

    def __init__(self, recorder: VideoRecorder, sm: StateMachine) -> None:
        self.recorder = recorder
        self.sm = sm
        self.logger = get_logger()

    def execute(self) -> Path:
        """録画を停止し、動画ファイルパスを返す。"""
        self.logger.info("録画停止")
        video = self.recorder.stop()
        self.sm.handle(Event.EARLY_ABORT)
        return video
