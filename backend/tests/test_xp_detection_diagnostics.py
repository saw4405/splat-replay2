from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import numpy as np
import pytest

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
from splat_replay.domain.ports import ImageMatcherPort, OCRPort
from splat_replay.domain.ports.image_editor import ImageEditorFactory
from splat_replay.domain.services import FrameAnalyzer, RecordState
from splat_replay.domain.services.analyzers.battle_analyzer import (
    BattleFrameAnalyzer,
)
from splat_replay.domain.services.analyzers.xp_detection import (
    XPExtractionDiagnostics,
)
from splat_replay.infrastructure.adapters.diagnostics import xp_detection


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


def _diagnostics_record() -> XPDetectionDiagnosticsRecord:
    return XPDetectionDiagnosticsRecord(
        timestamp=datetime(2026, 5, 28, 12, 34, 56),
        phase="STANDBY",
        record_state="STOPPED",
        match_select_detected=True,
        detected_game_mode="BATTLE",
        detected_match="X",
        matching_start_detected=False,
        ocr_text="2219.8\n",
        parsed_xp=2219.8,
        validation_error=None,
        accepted_xp="2219.8",
        previous_rate="1971.9",
        previous_xp=1971.9,
        delta_from_previous_xp=247.9,
        previous_candidate_xp=None,
        delta_from_previous_candidate_xp=None,
        same_candidate_count=1,
        metadata_will_update=True,
        xp_roi=_frame(10),
        xp_processed=_frame(255, (8, 8)),
        x_select_roi=_frame(120),
    )


def test_file_xp_detection_diagnostics_skips_when_output_root_missing(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "missing"
    monkeypatch.setattr(
        xp_detection, "XP_DETECTION_DIAGNOSTICS_DIR", output_root
    )

    writer = xp_detection.FileXPDetectionDiagnostics()

    assert not writer.is_enabled()
    assert writer.record(_diagnostics_record()) is None
    assert not output_root.exists()


def test_file_xp_detection_diagnostics_writes_jsonl_and_roi_images(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "xp_detection_diagnostics"
    output_root.mkdir()
    monkeypatch.setattr(
        xp_detection, "XP_DETECTION_DIAGNOSTICS_DIR", output_root
    )
    writer = xp_detection.FileXPDetectionDiagnostics()

    output_dir = writer.record(_diagnostics_record())

    assert output_dir is not None
    session_dirs = list(output_root.iterdir())
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]
    jsonl_path = session_dir / "events.jsonl"
    assert jsonl_path.is_file()
    assert (session_dir / "000001_xp_roi.png").is_file()
    assert (session_dir / "000001_xp_processed.png").is_file()
    assert (session_dir / "000001_x_select_roi.png").is_file()

    jsonl = jsonl_path.read_text(encoding="utf-8")
    assert '"ocr_text": "2219.8\\n"' in jsonl
    assert '"delta_from_previous_xp": 247.9' in jsonl
    assert '"xp_roi_gray_std"' in jsonl
    assert '"x_select_roi_hsv_mean"' in jsonl
    assert '"x_select_x_battle_hsv_match_ratio"' in jsonl


class _Matcher:
    async def match(self, key: str, image: Frame) -> bool:
        _ = key, image
        return False

    async def matched_name(self, group: str, image: Frame) -> str | None:
        _ = group, image
        return None


class _OCR:
    def __init__(self, text: str | None) -> None:
        self._text = text

    async def recognize_text(
        self,
        image: Frame,
        ps_mode: str | None = None,
        whitelist: str | None = None,
    ) -> str | None:
        _ = image, ps_mode, whitelist
        return self._text


class _ImageEditor:
    def __init__(self, image: Frame) -> None:
        self._image = image

    @property
    def image(self) -> Frame:
        return self._image

    def rotate(self, angle: float) -> "_ImageEditor":
        _ = angle
        return self

    def resize(self, scale_x: float, scale_y: float) -> "_ImageEditor":
        _ = scale_x, scale_y
        return self

    def padding(
        self,
        top: int,
        bottom: int,
        left: int,
        right: int,
        color: tuple[int, int, int] = (255, 255, 255),
    ) -> "_ImageEditor":
        _ = top, bottom, left, right, color
        return self

    def binarize(self) -> "_ImageEditor":
        return self

    def erode(
        self, kernel_size: tuple[int, int] = (2, 2), iterations: int = 1
    ) -> "_ImageEditor":
        _ = kernel_size, iterations
        return self

    def invert(self) -> "_ImageEditor":
        return self


def _battle_analyzer_with_ocr(text: str | None) -> BattleFrameAnalyzer:
    return BattleFrameAnalyzer(
        matcher=cast(ImageMatcherPort, _Matcher()),
        ocr=cast(OCRPort, _OCR(text)),
        image_editor_factory=cast(ImageEditorFactory, _ImageEditor),
    )


@pytest.mark.asyncio
async def test_extract_xp_rejects_ocr_text_without_single_decimal() -> None:
    analyzer = _battle_analyzer_with_ocr("2800\n")

    xp = await analyzer.extract_xp(_frame(0, (1080, 1920, 3)))

    assert xp is None


@pytest.mark.asyncio
async def test_extract_xp_diagnostics_reports_invalid_ocr_format() -> None:
    analyzer = _battle_analyzer_with_ocr("2800\n")

    diagnostics = await analyzer.extract_xp_diagnostics(
        _frame(0, (1080, 1920, 3))
    )

    assert diagnostics.ocr_text == "2800\n"
    assert diagnostics.parsed_xp is None
    assert diagnostics.xp is None
    assert diagnostics.validation_error == "XP_OCR_INVALID_FORMAT"


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
