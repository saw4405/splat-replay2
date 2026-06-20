from __future__ import annotations

import numpy as np
import pytest
from typing import cast

from splat_replay.application.interfaces import (
    EventBusPort,
    LoggerPort,
)
from splat_replay.application.interfaces.xp_detection_diagnostics import (
    XPDetectionDiagnosticsPort,
    XPDetectionDiagnosticsRecord,
)
from splat_replay.application.services.recording.standby_handler import (
    StandbyPhaseHandler,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.domain.models import (
    Frame,
    GameMode,
    Match,
    RateBase,
    RecordingMetadata,
    Udemae,
    XP,
    as_frame,
)
from splat_replay.domain.services import FrameAnalyzer, RecordState
from splat_replay.domain.services.analyzers.xp_detection import (
    XPExtractionDiagnostics,
)


class _Logger:
    def __init__(self) -> None:
        self.debug_events: list[tuple[str, dict[str, object]]] = []

    def debug(self, event: str, **kw: object) -> None:
        self.debug_events.append((event, kw))

    def info(self, event: str, **kw: object) -> None:
        pass

    def warning(self, event: str, **kw: object) -> None:
        pass

    def error(self, event: str, **kw: object) -> None:
        pass

    def exception(self, event: str, **kw: object) -> None:
        pass


class _EventBus:
    def __init__(self) -> None:
        self.domain_events: list[object] = []

    def publish(
        self, type_: str, payload: dict[str, object] | None = None
    ) -> None:
        pass

    def publish_domain_event(self, event: object) -> None:
        self.domain_events.append(event)

    def subscribe(self, event_types: object | None = None) -> object:
        raise NotImplementedError


def _frame(value: int, shape: tuple[int, ...] = (8, 8, 3)) -> Frame:
    return as_frame(np.full(shape, value, dtype=np.uint8))


class _Analyzer:
    def __init__(self) -> None:
        self.matching_start_detected = False

    async def detect_match_select(self, frame: Frame) -> bool:
        _ = frame
        return True

    async def extract_game_mode(self, frame: Frame) -> GameMode:
        _ = frame
        return GameMode.BATTLE

    async def extract_match_select(
        self, frame: Frame, mode: GameMode
    ) -> Match | None:
        _ = frame, mode
        return Match.X

    async def extract_xp_diagnostics(
        self, frame: Frame
    ) -> XPExtractionDiagnostics:
        _ = frame
        return XPExtractionDiagnostics(
            xp_roi=_frame(30),
            xp_processed=_frame(255, (8, 8)),
            ocr_text="2219.8\n",
            parsed_xp=2219.8,
            xp=XP(2219.8),
            validation_error=None,
        )

    async def extract_rate(
        self, frame: Frame, mode: GameMode
    ) -> RateBase | None:
        _ = frame, mode
        return XP(2219.8)

    async def extract_rate_for_match(
        self, frame: Frame, mode: GameMode, match: Match
    ) -> RateBase | None:
        _ = frame, mode, match
        return XP(2219.8)

    async def detect_matching_start(self, frame: Frame) -> bool:
        _ = frame
        return self.matching_start_detected


class _FailingDiagnosticsAnalyzer(_Analyzer):
    async def extract_xp_diagnostics(
        self, frame: Frame
    ) -> XPExtractionDiagnostics:
        _ = frame
        raise RuntimeError("diagnostics failed")


class _AnarchyAnalyzer(_Analyzer):
    async def extract_match_select(
        self, frame: Frame, mode: GameMode
    ) -> Match | None:
        _ = frame, mode
        return Match.ANARCHY

    async def extract_rate(
        self, frame: Frame, mode: GameMode
    ) -> RateBase | None:
        _ = frame, mode
        return Udemae("S+")

    async def extract_rate_for_match(
        self, frame: Frame, mode: GameMode, match: Match
    ) -> RateBase | None:
        _ = frame, mode, match
        return Udemae("S+")


class _DiagnosticsSink:
    def __init__(self) -> None:
        self.records: list[XPDetectionDiagnosticsRecord] = []

    def is_enabled(self) -> bool:
        return True

    def record(self, record: XPDetectionDiagnosticsRecord) -> str | None:
        self.records.append(record)
        return "diagnostics/session"


@pytest.mark.asyncio
async def test_standby_handler_records_xp_diagnostics_with_previous_rate_delta() -> (
    None
):
    diagnostics = _DiagnosticsSink()
    logger = _Logger()
    handler = StandbyPhaseHandler(
        cast(FrameAnalyzer, _Analyzer()),
        cast(LoggerPort, logger),
        cast(EventBusPort, _EventBus()),
        xp_detection_diagnostics=cast(XPDetectionDiagnosticsPort, diagnostics),
    )
    frame = _frame(0, (1080, 1920, 3))
    metadata = RecordingMetadata(rate=XP(1971.9))

    command = await handler.handle(
        frame,
        RecordingContext(metadata=metadata),
        RecordState.STOPPED,
    )

    assert command.updated_context.metadata.rate == XP(1971.9)
    assert command.updated_context.rate_candidate_for(Match.X) == XP(2219.8)
    assert len(diagnostics.records) == 1
    record = diagnostics.records[0]
    assert record.previous_rate == "1971.9"
    assert record.previous_xp == 1971.9
    assert record.validation_error is None
    assert record.delta_from_previous_xp == pytest.approx(247.9)
    assert record.previous_candidate_xp is None
    assert record.same_candidate_count == 1
    assert record.metadata_will_update is False
    assert logger.debug_events == []


@pytest.mark.asyncio
async def test_standby_handler_falls_back_to_normal_rate_extraction_when_diagnostics_fails() -> (
    None
):
    diagnostics = _DiagnosticsSink()
    handler = StandbyPhaseHandler(
        cast(FrameAnalyzer, _FailingDiagnosticsAnalyzer()),
        cast(LoggerPort, _Logger()),
        cast(EventBusPort, _EventBus()),
        xp_detection_diagnostics=cast(XPDetectionDiagnosticsPort, diagnostics),
    )
    frame = _frame(0, (1080, 1920, 3))
    metadata = RecordingMetadata(rate=XP(1971.9))

    command = await handler.handle(
        frame,
        RecordingContext(metadata=metadata),
        RecordState.STOPPED,
    )

    assert command.updated_context.metadata.rate == XP(1971.9)
    assert command.updated_context.rate_candidate_for(Match.X) == XP(2219.8)
    assert diagnostics.records == []


@pytest.mark.asyncio
async def test_standby_handler_tracks_anarchy_rank_as_shared_candidate() -> (
    None
):
    handler = StandbyPhaseHandler(
        cast(FrameAnalyzer, _AnarchyAnalyzer()),
        cast(LoggerPort, _Logger()),
        cast(EventBusPort, _EventBus()),
    )
    frame = _frame(0, (1080, 1920, 3))

    command = await handler.handle(
        frame,
        RecordingContext(),
        RecordState.STOPPED,
    )

    assert command.updated_context.metadata.rate is None
    assert command.updated_context.rate_candidate_for(Match.ANARCHY_OPEN) == (
        Udemae("S+")
    )
    assert command.updated_context.rate_candidate_for(
        Match.ANARCHY_SERIES
    ) == (Udemae("S+"))
