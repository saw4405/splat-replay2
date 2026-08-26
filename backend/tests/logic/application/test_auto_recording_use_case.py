from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Awaitable, Callable, cast

import numpy as np
import pytest

from splat_replay.application.interfaces import (
    CaptureDevicePort,
    CapturePort,
    LoggerPort,
)
from splat_replay.application.services.recording.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.application.services.recording.frame_processing_service import (
    FrameProcessingService,
)
from splat_replay.application.services.recording.commands import (
    RecordingCommand,
)
from splat_replay.application.services.recording.recording_context import (
    MatchRateCandidate,
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
from splat_replay.domain.models import (
    Frame,
    Match,
    RecordingMetadata,
    SwitchPowerState,
    XP,
)
from splat_replay.domain.services import RecordState


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
        self.handle_frame_calls = 0
        self.handled_frames: list[Frame] = []

    async def handle_frame(
        self, frame: Frame, context: RecordingContext, state: RecordState
    ) -> RecordingCommand:
        _ = state
        self.handle_frame_calls += 1
        self.handled_frames.append(frame)
        return RecordingCommand.none(context)

    async def drain_weapon_detection_completed(
        self, context: RecordingContext
    ) -> RecordingContext:
        self._events.append("drain")
        self.drain_contexts.append(context)
        return self._drained_context

    def cancel_background_tasks(self) -> None:
        self._events.append("cancel")
        self.cancel_calls += 1


class _CaptureIntervalSpy:
    def __init__(self) -> None:
        self.intervals: list[float] = []

    def set_capture_interval(self, interval_seconds: float) -> None:
        self.intervals.append(interval_seconds)


class _SessionSpy:
    state: RecordState

    def __init__(self, *, events: list[str]) -> None:
        self._events = events
        self.updated_contexts: list[RecordingContext] = []
        self.context_at_stop: RecordingContext | None = None
        self.result_frame_at_stop: Frame | None = None
        self.state = RecordState.RECORDING

    @property
    def context(self) -> RecordingContext:
        return (
            self.updated_contexts[-1]
            if self.updated_contexts
            else RecordingContext()
        )

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


def test_is_reset_context_returns_false_when_rate_candidates_exist() -> None:
    context = RecordingContext(
        rate_candidates=(MatchRateCandidate(Match.X, XP(2219.8)),)
    )

    assert AutoRecordingUseCase._is_reset_context(context) is False


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


class _DummyFrameProcessorWithException:
    def __init__(
        self,
        frames: list[Frame | None],
        on_second_call: Callable[[], None] | None = None,
    ) -> None:
        self._frames = list(frames)
        self.observe_power_off_calls = 0
        self.on_second_call = on_second_call

    async def acquire_frame(self) -> Frame | None:
        return self._frames.pop(0) if self._frames else None

    async def observe_power_off(
        self,
        frame: Frame,
        last_check: float,
        check_interval_seconds: float = 5.0,
    ) -> tuple[float, bool | None]:
        _ = frame, check_interval_seconds
        self.observe_power_off_calls += 1
        if self.observe_power_off_calls == 1:
            raise RuntimeError("Simulated crash in OpenCV frame check")
        if self.observe_power_off_calls == 2 and self.on_second_call:
            self.on_second_call()
        return last_check, False


@pytest.mark.asyncio
async def test_main_loop_recovers_from_analysis_exception() -> None:
    events: list[str] = []
    frame1 = np.zeros((2, 2, 3), dtype=np.uint8)
    frame2 = np.ones((2, 2, 3), dtype=np.uint8)
    frame3 = np.ones((2, 2, 3), dtype=np.uint8) * 2
    processor = _DummyFrameProcessorWithException(
        [frame1, frame2, frame3, None]
    )

    session = _SessionSpy(events=events)
    session.state = RecordState.STOPPED

    phase_handlers = _PhaseHandlersSpy(
        drained_context=RecordingContext(),
        events=events,
    )

    class _FrameProcessorStub:
        def __init__(self, impl: _DummyFrameProcessorWithException) -> None:
            self._impl = impl

        async def acquire_frame(self) -> Frame | None:
            return await self._impl.acquire_frame()

        async def observe_power_off(
            self,
            frame: Frame,
            last_check: float,
            check_interval_seconds: float = 5.0,
        ) -> tuple[float, bool | None]:
            return await self._impl.observe_power_off(
                frame, last_check, check_interval_seconds
            )

    use_case = AutoRecordingUseCase(
        session_service=cast(RecordingSessionService, session),
        frame_processor=cast(
            FrameProcessingService, _FrameProcessorStub(processor)
        ),
        phase_handlers=cast(PhaseHandlerRegistry, phase_handlers),
        context=RecordingContext(),
        capture=cast(CapturePort, object()),
        capture_producer=cast(FrameCaptureProducer, object()),
        publisher_worker=cast(PublisherWorker, object()),
        logger=cast(LoggerPort, _LoggerStub()),
    )

    processor.on_second_call = lambda: use_case._stop_event.set()
    await use_case._run_main_loop()

    assert processor.observe_power_off_calls == 2


class _PowerCycleFrameProcessor:
    def __init__(self, observations: list[bool]) -> None:
        self._observations = list(observations)
        self._next_index = 0
        self.power_off_events = 0
        self.check_intervals: list[float] = []
        self.use_case: AutoRecordingUseCase | None = None

    async def acquire_frame(self) -> Frame | None:
        return np.zeros((2, 2, 3), dtype=np.uint8)

    async def observe_power_off(
        self,
        frame: Frame,
        last_check: float,
        check_interval_seconds: float = 5.0,
    ) -> tuple[float, bool | None]:
        _ = frame
        self.check_intervals.append(check_interval_seconds)
        observation = self._observations[self._next_index]
        self._next_index += 1
        if self._next_index == len(self._observations):
            assert self.use_case is not None
            self.use_case._stop_event.set()
        return last_check, observation

    def publish_power_off_detected(self, final: bool = False) -> None:
        assert final is True
        self.power_off_events += 1


@pytest.mark.asyncio
async def test_main_loop_rearms_for_three_power_cycles() -> None:
    events: list[str] = []
    observations = [
        *([False] * 3),
        *([True] * 6),
        *([False] * 3),
        *([True] * 3),
        *([False] * 3),
        *([True] * 3),
        *([False] * 3),
    ]
    processor = _PowerCycleFrameProcessor(observations)
    session = _SessionSpy(events=events)
    session.state = RecordState.STOPPED
    phase_handlers = _PhaseHandlersSpy(
        drained_context=RecordingContext(), events=events
    )
    capture_producer = _CaptureIntervalSpy()
    use_case = AutoRecordingUseCase(
        session_service=cast(RecordingSessionService, session),
        frame_processor=cast(FrameProcessingService, processor),
        phase_handlers=cast(PhaseHandlerRegistry, phase_handlers),
        context=RecordingContext(),
        capture=cast(CapturePort, object()),
        capture_producer=cast(FrameCaptureProducer, capture_producer),
        publisher_worker=cast(PublisherWorker, object()),
        logger=cast(LoggerPort, _LoggerStub()),
    )
    processor.use_case = use_case

    saw_power_off = await use_case._run_main_loop()

    assert saw_power_off is True
    assert use_case.power_status() is SwitchPowerState.ARMED
    assert processor.power_off_events == 3
    assert phase_handlers.handle_frame_calls > 0
    assert processor.check_intervals == [
        *([0.0] * 3),
        *([5.0] * 3),
        *([0.0] * 6),
        *([5.0] * 3),
        *([0.0] * 3),
        *([5.0] * 3),
        *([0.0] * 3),
    ]
    assert capture_producer.intervals == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0]


@pytest.mark.asyncio
async def test_main_loop_replays_all_frames_used_to_confirm_power_on() -> None:
    events: list[str] = []
    on_candidate_frames = [
        np.full((2, 2, 3), fill_value=value, dtype=np.uint8)
        for value in (1, 2, 3)
    ]

    class _OnCandidateFrameProcessor:
        def __init__(self) -> None:
            self.frames = list(on_candidate_frames)
            self.use_case: AutoRecordingUseCase | None = None

        async def acquire_frame(self) -> Frame | None:
            if self.frames:
                return self.frames.pop(0)
            assert self.use_case is not None
            self.use_case._stop_event.set()
            return None

        async def observe_power_off(
            self,
            frame: Frame,
            last_check: float,
            check_interval_seconds: float = 5.0,
        ) -> tuple[float, bool | None]:
            _ = frame, check_interval_seconds
            return last_check, False

    processor = _OnCandidateFrameProcessor()
    session = _SessionSpy(events=events)
    session.state = RecordState.STOPPED
    phase_handlers = _PhaseHandlersSpy(
        drained_context=RecordingContext(), events=events
    )
    capture_producer = _CaptureIntervalSpy()
    use_case = AutoRecordingUseCase(
        session_service=cast(RecordingSessionService, session),
        frame_processor=cast(FrameProcessingService, processor),
        phase_handlers=cast(PhaseHandlerRegistry, phase_handlers),
        context=RecordingContext(),
        capture=cast(CapturePort, object()),
        capture_producer=cast(FrameCaptureProducer, capture_producer),
        publisher_worker=cast(PublisherWorker, object()),
        logger=cast(LoggerPort, _LoggerStub()),
    )
    use_case._last_record_state = RecordState.STOPPED
    processor.use_case = use_case

    await use_case._run_main_loop()

    assert len(phase_handlers.handled_frames) == 3
    assert all(
        handled is expected
        for handled, expected in zip(
            phase_handlers.handled_frames,
            on_candidate_frames,
            strict=True,
        )
    )
    assert capture_producer.intervals == [0.0]


@pytest.mark.asyncio
async def test_capture_disconnect_does_not_publish_power_off() -> None:
    events: list[str] = []

    class _NoFrameProcessor:
        def __init__(self) -> None:
            self.power_off_events = 0

        async def acquire_frame(self) -> Frame | None:
            return None

        def publish_power_off_detected(self, final: bool = False) -> None:
            _ = final
            self.power_off_events += 1

    class _DisconnectedDevice:
        def is_connected(self) -> bool:
            use_case._stop_event.set()
            return False

    processor = _NoFrameProcessor()
    session = _SessionSpy(events=events)
    session.state = RecordState.STOPPED
    phase_handlers = _PhaseHandlersSpy(
        drained_context=RecordingContext(), events=events
    )
    capture_producer = _CaptureIntervalSpy()
    use_case = AutoRecordingUseCase(
        session_service=cast(RecordingSessionService, session),
        frame_processor=cast(FrameProcessingService, processor),
        phase_handlers=cast(PhaseHandlerRegistry, phase_handlers),
        context=RecordingContext(),
        capture=cast(CapturePort, object()),
        capture_producer=cast(FrameCaptureProducer, capture_producer),
        publisher_worker=cast(PublisherWorker, object()),
        logger=cast(LoggerPort, _LoggerStub()),
        capture_device=cast(CaptureDevicePort, _DisconnectedDevice()),
    )

    saw_power_off = await use_case._run_main_loop()

    assert saw_power_off is False
    assert use_case.power_status() is SwitchPowerState.CAPTURE_DISCONNECTED
    assert processor.power_off_events == 0
    assert capture_producer.intervals == [1.0]


@pytest.mark.asyncio
async def test_background_recorder_retries_after_setup_failure() -> None:
    events: list[str] = []

    class _RetrySession(_SessionSpy):
        def __init__(self) -> None:
            super().__init__(events=events)
            self.state = RecordState.STOPPED
            self.setup_calls = 0

        async def setup(self) -> None:
            self.setup_calls += 1
            if self.setup_calls == 1:
                raise RuntimeError("OBS unavailable")

        async def teardown(self) -> None:
            return None

    class _Capture:
        def setup(self) -> None:
            return None

        def teardown(self) -> None:
            return None

    class _Worker:
        def set_capture_interval(self, interval_seconds: float) -> None:
            _ = interval_seconds

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

    session = _RetrySession()
    phase_handlers = _PhaseHandlersSpy(
        drained_context=RecordingContext(), events=events
    )
    use_case = AutoRecordingUseCase(
        session_service=cast(RecordingSessionService, session),
        frame_processor=cast(FrameProcessingService, object()),
        phase_handlers=cast(PhaseHandlerRegistry, phase_handlers),
        context=RecordingContext(),
        capture=cast(CapturePort, _Capture()),
        capture_producer=cast(FrameCaptureProducer, _Worker()),
        publisher_worker=cast(PublisherWorker, _Worker()),
        logger=cast(LoggerPort, _LoggerStub()),
        background_retry_delay_seconds=0.0,
    )

    async def stop_after_retry(*, continuous: bool = True) -> bool:
        _ = continuous
        use_case.force_stop()
        return False

    original_run_main_loop = use_case._run_main_loop

    async def run_main_loop_after_setup(*, continuous: bool = True) -> bool:
        if session.setup_calls >= 2:
            return await stop_after_retry(continuous=continuous)
        return await original_run_main_loop(continuous=continuous)

    use_case._run_main_loop = (  # type: ignore[method-assign]
        run_main_loop_after_setup
    )

    assert await use_case.start_background() is True
    task = use_case._task
    assert task is not None
    await asyncio.wait_for(task, timeout=1)

    assert session.setup_calls == 2
    assert use_case.status() == "stopped"


@pytest.mark.asyncio
async def test_stop_background_waits_for_recorder_cleanup() -> None:
    events: list[str] = []
    setup_completed = asyncio.Event()

    class _Session:
        state = RecordState.STOPPED

        async def setup(self) -> None:
            events.append("session_setup")

        async def teardown(self) -> None:
            events.append("session_teardown")

    class _Capture:
        def setup(self) -> None:
            events.append("capture_setup")
            setup_completed.set()

        def teardown(self) -> None:
            events.append("capture_teardown")

    class _Worker:
        def __init__(self, name: str) -> None:
            self.name = name

        def set_capture_interval(self, interval_seconds: float) -> None:
            events.append(f"{self.name}_interval_{interval_seconds:.1f}")

        def start(self) -> None:
            events.append(f"{self.name}_start")

        def stop(self) -> None:
            events.append(f"{self.name}_stop")

    class _NoFrameProcessor:
        async def acquire_frame(self) -> Frame | None:
            return None

    phase_handlers = _PhaseHandlersSpy(
        drained_context=RecordingContext(), events=events
    )
    use_case = AutoRecordingUseCase(
        session_service=cast(RecordingSessionService, _Session()),
        frame_processor=cast(FrameProcessingService, _NoFrameProcessor()),
        phase_handlers=cast(PhaseHandlerRegistry, phase_handlers),
        context=RecordingContext(),
        capture=cast(CapturePort, _Capture()),
        capture_producer=cast(FrameCaptureProducer, _Worker("capture")),
        publisher_worker=cast(PublisherWorker, _Worker("publisher")),
        logger=cast(LoggerPort, _LoggerStub()),
    )

    assert await use_case.start_background() is True
    await asyncio.wait_for(setup_completed.wait(), timeout=1)

    await asyncio.wait_for(use_case.stop_background(), timeout=1)

    assert use_case.status() == "stopped"
    assert use_case.power_status() is SwitchPowerState.STOPPED
    assert events == [
        "session_setup",
        "capture_setup",
        "publisher_start",
        "capture_interval_1.0",
        "capture_start",
        "cancel",
        "capture_stop",
        "publisher_stop",
        "capture_teardown",
        "session_teardown",
    ]
