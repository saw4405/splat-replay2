from __future__ import annotations

import numpy as np
import pytest
from typing import cast

from splat_replay.domain.models import Frame, as_frame, XP
from splat_replay.domain.ports import ImageMatcherPort, OCRPort
from splat_replay.domain.ports.image_editor import ImageEditorFactory
from splat_replay.domain.services.analyzers.battle_analyzer import (
    BattleFrameAnalyzer,
)


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

    def binarize(self, threshold: int | None = None) -> "_ImageEditor":
        _ = threshold
        return self

    def erode(
        self, kernel_size: tuple[int, int] = (2, 2), iterations: int = 1
    ) -> "_ImageEditor":
        _ = kernel_size, iterations
        return self

    def invert(self) -> "_ImageEditor":
        return self

    def count_connected_components(
        self, *, foreground_threshold: int, min_area: int
    ) -> int:
        if self._image.ndim == 3:
            foreground = np.any(self._image < foreground_threshold, axis=2)
        else:
            foreground = self._image < foreground_threshold
        height, width = foreground.shape[:2]
        visited = np.zeros((height, width), dtype=np.bool_)
        component_count = 0
        for y in range(height):
            for x in range(width):
                if visited[y, x] or not foreground[y, x]:
                    continue
                area = 0
                stack = [(x, y)]
                visited[y, x] = True
                while stack:
                    current_x, current_y = stack.pop()
                    area += 1
                    for next_y in range(current_y - 1, current_y + 2):
                        if next_y < 0 or next_y >= height:
                            continue
                        for next_x in range(current_x - 1, current_x + 2):
                            if next_x < 0 or next_x >= width:
                                continue
                            if (
                                visited[next_y, next_x]
                                or not foreground[next_y, next_x]
                            ):
                                continue
                            visited[next_y, next_x] = True
                            stack.append((next_x, next_y))
                if area >= min_area:
                    component_count += 1
        return component_count


class _FixedThresholdImageEditor(_ImageEditor):
    def __init__(self, image: Frame) -> None:
        super().__init__(image)
        self._component_count = 4

    def binarize(
        self, threshold: int | None = None
    ) -> "_FixedThresholdImageEditor":
        self._component_count = 6 if threshold == 115 else 4
        return self

    def count_connected_components(
        self, *, foreground_threshold: int, min_area: int
    ) -> int:
        _ = foreground_threshold, min_area
        return self._component_count


def _frame(value: int, shape: tuple[int, ...] = (8, 8, 3)) -> Frame:
    return as_frame(np.full(shape, value, dtype=np.uint8))


def _xp_frame_with_dark_components(component_count: int) -> Frame:
    frame = np.full((1080, 1920, 3), 255, dtype=np.uint8)
    for index in range(component_count):
        left = 1732 + (index * 20)
        frame[200:210, left : left + 10] = 0
    return as_frame(frame)


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


@pytest.mark.asyncio
async def test_extract_xp_rejects_valid_decimal_when_components_are_merged() -> (
    None
):
    analyzer = _battle_analyzer_with_ocr("2000.1\n")

    xp = await analyzer.extract_xp(_xp_frame_with_dark_components(4))

    assert xp is None


@pytest.mark.asyncio
async def test_extract_xp_uses_fixed_threshold_for_binarization() -> None:
    analyzer = BattleFrameAnalyzer(
        matcher=cast(ImageMatcherPort, _Matcher()),
        ocr=cast(OCRPort, _OCR("2109.1\n")),
        image_editor_factory=cast(
            ImageEditorFactory, _FixedThresholdImageEditor
        ),
    )

    xp = await analyzer.extract_xp(_frame(0, (1080, 1920, 3)))

    assert xp == XP(2109.1)


@pytest.mark.asyncio
async def test_extract_xp_accepts_valid_decimal_when_components_match() -> (
    None
):
    analyzer = _battle_analyzer_with_ocr("2109.1\n")

    xp = await analyzer.extract_xp(_xp_frame_with_dark_components(6))

    assert xp == XP(2109.1)


@pytest.mark.asyncio
async def test_extract_xp_accepts_valid_three_digit_decimal_when_five_components_match() -> (
    None
):
    analyzer = _battle_analyzer_with_ocr("500.0\n")

    xp = await analyzer.extract_xp(_xp_frame_with_dark_components(5))

    assert xp == XP(500.0)


@pytest.mark.asyncio
async def test_extract_xp_rejects_valid_decimal_when_component_count_is_unexpected() -> (
    None
):
    analyzer = _battle_analyzer_with_ocr("2109.1\n")

    xp = await analyzer.extract_xp(_xp_frame_with_dark_components(7))

    assert xp is None


@pytest.mark.asyncio
async def test_extract_xp_diagnostics_reports_component_count_mismatch() -> (
    None
):
    analyzer = _battle_analyzer_with_ocr("2000.1\n")

    diagnostics = await analyzer.extract_xp_diagnostics(
        _xp_frame_with_dark_components(4)
    )

    assert diagnostics.ocr_text == "2000.1\n"
    assert diagnostics.parsed_xp == 2000.1
    assert diagnostics.xp is None
    assert diagnostics.validation_error == "XP_OCR_COMPONENT_COUNT_MISMATCH"
    assert diagnostics.xp_processed_connected_component_count == 4
