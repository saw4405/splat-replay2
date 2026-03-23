from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.use_cases.auto_recording_use_case import (
    AutoRecordingUseCase,
)


def test_is_reset_context_returns_true_for_default_context() -> None:
    assert AutoRecordingUseCase._is_reset_context(RecordingContext()) is True
