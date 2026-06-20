from __future__ import annotations

# ruff: noqa: E402
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

try:
    import pytesseract
except ImportError:
    HAS_TESSERACT = False
else:
    try:
        pytesseract.get_tesseract_version()
        HAS_TESSERACT = True
    except pytesseract.TesseractNotFoundError:
        HAS_TESSERACT = False

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))  # noqa: E402

from splat_replay.domain.config import ImageMatchingSettings  # noqa: E402
from splat_replay.domain.models import (  # noqa: E402
    XP,
    GameMode,
    Match,
    as_frame,
)
from splat_replay.domain.services.analyzers import (  # noqa: E402
    BattleFrameAnalyzer,
    FrameAnalyzer,
    SalmonFrameAnalyzer,
)
from splat_replay.infrastructure import MatcherRegistry, TesseractOCR  # noqa: E402
from splat_replay.infrastructure.adapters.image import ImageEditor  # noqa: E402


class DummyOCR:
    def recognize_text_sync(
        self,
        image: np.ndarray,
        ps_mode: str | None = None,
        whitelist: str | None = None,
    ) -> str | None:
        _ = image, ps_mode, whitelist
        return None

    async def recognize_text(
        self,
        image: np.ndarray,
        ps_mode: str | None = None,
        whitelist: str | None = None,
    ) -> str | None:
        _ = image, ps_mode, whitelist
        return None


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "fixtures" / "templates"
MATCHER_SETTINGS = ImageMatchingSettings.load_from_yaml(
    BASE_DIR.parent / "config" / "image_matching.yaml"
)


def _create_analyzer() -> FrameAnalyzer:
    matcher_registry = MatcherRegistry(MATCHER_SETTINGS)
    ocr = TesseractOCR() if HAS_TESSERACT else DummyOCR()
    battle = BattleFrameAnalyzer(
        matcher_registry,
        ocr,
        lambda image: ImageEditor(image),
    )
    salmon = SalmonFrameAnalyzer(matcher_registry)
    return FrameAnalyzer(battle, salmon, matcher_registry)


def _load_image(filename: str) -> np.ndarray:
    image = cv2.imread(str(TEMPLATE_DIR / filename))
    if image is None:
        pytest.fail(f"fixture image is missing: {filename}")
    return as_frame(image)


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract OCR is not installed")
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("rate_event_power_2105.7.png", XP(2105.7)),
        ("rate_event_power_2157.9.png", XP(2157.9)),
        ("rate_event_power_2180.0.png", XP(2180.0)),
    ],
)
async def test_extract_event_power_from_match_select_screen(
    filename: str,
    expected: XP,
) -> None:
    analyzer = _create_analyzer()
    frame = _load_image(filename)

    assert await analyzer.detect_match_select(frame)
    mode = await analyzer.extract_game_mode(frame)
    assert mode is GameMode.BATTLE
    match = await analyzer.extract_match_select(frame, mode)
    assert match is Match.CHALLENGE

    assert await analyzer.extract_rate(frame, mode) == expected


@pytest.mark.asyncio
async def test_extract_event_power_ignores_event_screen_without_label() -> (
    None
):
    analyzer = _create_analyzer()
    frame = _load_image("match_select_challenge.png")

    mode = await analyzer.extract_game_mode(frame)
    assert mode is GameMode.BATTLE
    match = await analyzer.extract_match_select(frame, mode)
    assert match is Match.CHALLENGE

    assert await analyzer.extract_rate(frame, mode) is None


@pytest.mark.asyncio
async def test_extract_event_power_ignores_non_event_screen() -> None:
    analyzer = _create_analyzer()
    frame = _load_image("rate_XP1971.9.png")

    assert (
        await analyzer.extract_rate_for_match(
            frame, GameMode.BATTLE, Match.CHALLENGE
        )
        is None
    )
