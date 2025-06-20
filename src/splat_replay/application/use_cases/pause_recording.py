"""録画を一時停止するユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import VideoRecorder
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.shared.logger import get_logger


class PauseRecordingUseCase:
    """録画を一時停止する。"""

    def __init__(self, recorder: VideoRecorder, sm: StateMachine) -> None:
        self.recorder = recorder
        self.sm = sm
        self.logger = get_logger()

    def execute(self) -> None:
        """録画を一時停止する。"""
        self.logger.info("一時停止")
        self.recorder.pause()
        self.sm.handle(Event.MANUAL_PAUSE)
