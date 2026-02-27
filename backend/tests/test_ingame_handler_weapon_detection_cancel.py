from __future__ import annotations

import time
from typing import Mapping, Optional, Set, cast

import numpy as np
import pytest

from splat_replay.application.interfaces import EventBusPort, LoggerPort
from splat_replay.application.interfaces.messaging import EventSubscription
from splat_replay.application.services.recording.commands import (
    RecordingAction,
)
from splat_replay.application.services.recording.ingame_handler import (
    InGamePhaseHandler,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.weapon_detection_service import (
    WeaponDetectionService,
)
from splat_replay.domain.events import DomainEvent
from splat_replay.domain.services import FrameAnalyzer, RecordState


class _DummyLogger:
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


class _DummySubscription:
    def poll(self, max_items: int = 100) -> list[object]:
        return []

    def close(self) -> None:
        return None


class _DummyBus:
    def publish(
        self, event_type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        return None

    def publish_domain_event(self, event: DomainEvent) -> None:
        return None

    def subscribe(
        self, event_types: Optional[Set[str]] = None
    ) -> EventSubscription:
        return _DummySubscription()


class _AnalyzerStub:
    def __init__(
        self,
        *,
        abort: bool = False,
        finish: bool = False,
        communication_error: bool = False,
    ) -> None:
        self.abort = abort
        self.finish = finish
        self.communication_error = communication_error

    async def detect_session_abort(
        self, frame: np.ndarray, gm: object
    ) -> bool:
        return self.abort

    async def detect_session_finish(
        self, frame: np.ndarray, gm: object
    ) -> bool:
        return self.finish

    async def detect_communication_error(
        self, frame: np.ndarray, gm: object
    ) -> bool:
        return self.communication_error

    async def detect_session_judgement(
        self, frame: np.ndarray, gm: object
    ) -> bool:
        return False


class _WeaponDetectionServiceSpy:
    def __init__(self) -> None:
        self.cancel_calls = 0
        self.process_calls = 0

    def request_cancel(self) -> None:
        self.cancel_calls += 1

    async def process(
        self,
        *,
        frame: np.ndarray,
        context: RecordingContext,
    ) -> RecordingContext:
        self.process_calls += 1
        return context


def _build_handler(
    *,
    analyzer: _AnalyzerStub,
    weapon_detection_service: _WeaponDetectionServiceSpy,
) -> InGamePhaseHandler:
    return InGamePhaseHandler(
        analyzer=cast(FrameAnalyzer, analyzer),
        logger=cast(LoggerPort, _DummyLogger()),
        event_bus=cast(EventBusPort, _DummyBus()),
        weapon_detection_service=cast(
            WeaponDetectionService,
            weapon_detection_service,
        ),
    )


def _frame() -> np.ndarray:
    return np.zeros((8, 8, 3), dtype=np.uint8)


@pytest.mark.asyncio
async def test_cancel_called_on_early_abort() -> None:
    analyzer = _AnalyzerStub(abort=True)
    weapon_service = _WeaponDetectionServiceSpy()
    handler = _build_handler(
        analyzer=analyzer,
        weapon_detection_service=weapon_service,
    )
    context = RecordingContext(battle_started_at=time.time() - 10.0)

    command = await handler.handle(_frame(), context, RecordState.RECORDING)

    assert command.action is RecordingAction.CANCEL_RECORDING
    assert weapon_service.cancel_calls == 1
    assert weapon_service.process_calls == 0


@pytest.mark.asyncio
async def test_cancel_called_on_time_limit() -> None:
    analyzer = _AnalyzerStub()
    weapon_service = _WeaponDetectionServiceSpy()
    handler = _build_handler(
        analyzer=analyzer,
        weapon_detection_service=weapon_service,
    )
    context = RecordingContext(battle_started_at=time.time() - 601.0)

    command = await handler.handle(_frame(), context, RecordState.RECORDING)

    assert command.action is RecordingAction.STOP_RECORDING
    assert weapon_service.cancel_calls == 1
    assert weapon_service.process_calls == 0


@pytest.mark.asyncio
async def test_cancel_called_on_finish() -> None:
    analyzer = _AnalyzerStub(finish=True)
    weapon_service = _WeaponDetectionServiceSpy()
    handler = _build_handler(
        analyzer=analyzer,
        weapon_detection_service=weapon_service,
    )
    context = RecordingContext(battle_started_at=time.time() - 120.0)

    command = await handler.handle(_frame(), context, RecordState.RECORDING)

    assert command.action is RecordingAction.PAUSE_RECORDING
    assert weapon_service.cancel_calls == 1
    assert weapon_service.process_calls == 1


@pytest.mark.asyncio
async def test_cancel_called_on_communication_error() -> None:
    analyzer = _AnalyzerStub(communication_error=True)
    weapon_service = _WeaponDetectionServiceSpy()
    handler = _build_handler(
        analyzer=analyzer,
        weapon_detection_service=weapon_service,
    )
    context = RecordingContext(battle_started_at=time.time() - 120.0)

    command = await handler.handle(_frame(), context, RecordState.RECORDING)

    assert command.action is RecordingAction.CANCEL_RECORDING
    assert weapon_service.cancel_calls == 1
    assert weapon_service.process_calls == 1
