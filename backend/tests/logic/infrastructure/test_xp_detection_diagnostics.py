from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import numpy as np
import pytest

from splat_replay.application.interfaces.xp_detection_diagnostics import (
    XPDetectionDiagnosticsRecord,
)
from splat_replay.domain.models import (
    Frame,
    as_frame,
)
from splat_replay.domain.ports import ImageMatcherPort, OCRPort
from splat_replay.domain.ports.image_editor import ImageEditorFactory
from splat_replay.domain.services.analyzers.battle_analyzer import (
    BattleFrameAnalyzer,
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
        xp_processed_connected_component_count=6,
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
    assert '"xp_processed_connected_component_count": 6' in jsonl
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
