"""録画を再開するユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import VideoRecorder
from splat_replay.domain.services.state_machine import Event, StateMachine


class ResumeRecordingUseCase:
    """録画を再開する。"""

    def __init__(self, recorder: VideoRecorder, sm: StateMachine) -> None:
        self.recorder = recorder
        self.sm = sm

    def execute(self) -> None:
        """録画を再開する。"""
        self.recorder.resume()
        self.sm.handle(Event.MANUAL_RESUME)
