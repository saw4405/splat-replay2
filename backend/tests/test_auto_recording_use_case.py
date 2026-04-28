from __future__ import annotations

from dataclasses import replace
from typing import Awaitable, Callable, cast

import numpy as np
import pytest

from splat_replay.application.interfaces import CapturePort, LoggerPort
from splat_replay.application.services.recording.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.application.services.recording.frame_processing_service import (
    FrameProcessingService,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.publisher_worker import (
    PublisherWorker,
)
from splat_replay.application.services.recording.phase_handler_registry import (
    PhaseHandlerRegistry,
)
from splat_replay.application.services.recording.recording_session_service import (
    RecordingSessionService,
)
from splat_replay.application.use_cases.auto_recording_use_case import (
    AutoRecordingUseCase,
)
from splat_replay.domain.models import Frame, RecordingMetadata


class _LoggerStub:
    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        return None

    def error(self, event: str, **kw: object) -> None:
        return None

    def exception(self, event: str, **kw: object) -> None:
        return None


class _PhaseHandlersSpy:
    def __init__(
        self,
        *,
        drained_context: RecordingContext,
        events: list[str],
    ) -> None:
        self._drained_context = drained_context
        self._events = events
        self.drain_contexts: list[RecordingContext] = []
        self.cancel_calls = 0

    async def drain_weapon_detection_completed(
        self, context: RecordingContext
    ) -> RecordingContext:
        self._events.append("drain")
        self.drain_contexts.append(context)
        return self._drained_context

    def cancel_background_tasks(self) -> None:
        self._events.append("cancel")
        self.cancel_calls += 1


class _SessionSpy:
    def __init__(self, *, events: list[str]) -> None:
        self._events = events
        self.updated_contexts: list[RecordingContext] = []
        self.context_at_stop: RecordingContext | None = None
        self.result_frame_at_stop: Frame | None = None

    def update_context(self, context: RecordingContext) -> None:
        self._events.append("update")
        self.updated_contexts.append(context)

    async def stop(
        self, get_result_frame: Callable[[], Awaitable[Frame | None]]
    ) -> None:
        self._events.append("stop")
        self.context_at_stop = self.updated_contexts[-1]
        self.result_frame_at_stop = await get_result_frame()


def test_is_reset_context_returns_true_for_default_context() -> None:
    assert AutoRecordingUseCase._is_reset_context(RecordingContext()) is True


@pytest.mark.asyncio
async def test_stop_recording_drains_weapon_detection_before_save_once() -> (
    None
):
    events: list[str] = []
    initial_context = RecordingContext(battle_started_at=1.0)
    drained_context = replace(
        initial_context,
        metadata=RecordingMetadata(
            allies=("known_ally_1", "", "", ""),
            enemies=("", "known_enemy_2", "", ""),
        ),
        weapon_detection_attempts=1,
    )
    session = _SessionSpy(events=events)
    phase_handlers = _PhaseHandlersSpy(
        drained_context=drained_context,
        events=events,
    )
    use_case = AutoRecordingUseCase(
        session_service=cast(RecordingSessionService, session),
        frame_processor=cast(FrameProcessingService, object()),
        phase_handlers=cast(PhaseHandlerRegistry, phase_handlers),
        context=initial_context,
        capture=cast(CapturePort, object()),
        capture_producer=cast(FrameCaptureProducer, object()),
        publisher_worker=cast(PublisherWorker, object()),
        logger=cast(LoggerPort, _LoggerStub()),
    )

    await use_case._handle_stop_recording()

    assert phase_handlers.drain_contexts == [initial_context]
    assert session.updated_contexts == [drained_context]
    assert session.context_at_stop == drained_context
    assert phase_handlers.cancel_calls == 1
    assert events == ["drain", "update", "stop", "cancel"]


@pytest.mark.asyncio
async def test_stop_recording_handles_result_frame_without_context_equality() -> (
    None
):
    events: list[str] = []
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    initial_context = RecordingContext(
        battle_started_at=1.0,
        result_frame=frame,
    )
    drained_context = replace(
        initial_context,
        weapon_detection_done=True,
    )
    session = _SessionSpy(events=events)
    session.update_context(initial_context)
    phase_handlers = _PhaseHandlersSpy(
        drained_context=drained_context,
        events=events,
    )
    use_case = AutoRecordingUseCase(
        session_service=cast(RecordingSessionService, session),
        frame_processor=cast(FrameProcessingService, object()),
        phase_handlers=cast(PhaseHandlerRegistry, phase_handlers),
        context=initial_context,
        capture=cast(CapturePort, object()),
        capture_producer=cast(FrameCaptureProducer, object()),
        publisher_worker=cast(PublisherWorker, object()),
        logger=cast(LoggerPort, _LoggerStub()),
    )

    await use_case._handle_stop_recording()

    assert len(phase_handlers.drain_contexts) == 1
    assert phase_handlers.drain_contexts[0] is initial_context
    assert len(session.updated_contexts) == 2
    assert session.updated_contexts[0] is initial_context
    assert session.updated_contexts[1].weapon_detection_done is True
    assert session.updated_contexts[1].result_frame is frame
    assert session.context_at_stop is not None
    assert session.context_at_stop.weapon_detection_done is True
    assert session.context_at_stop.result_frame is frame
    assert session.result_frame_at_stop is frame
    assert phase_handlers.cancel_calls == 1
    assert events == ["update", "drain", "update", "stop", "cancel"]
