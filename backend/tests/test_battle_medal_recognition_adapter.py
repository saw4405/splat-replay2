from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, cast

import cv2
import numpy as np
import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

from splat_replay.application.interfaces import LoggerPort  # noqa: E402
from splat_replay.domain.models import as_frame  # noqa: E402
from splat_replay.infrastructure.adapters.medal_detection import (  # noqa: E402
    BattleMedalRecognizerAdapter,
)

TEMPLATE_DIR = Path(__file__).resolve().parent / "fixtures" / "templates"


class _DummyLogger:
    def debug(self, event: str, **kw: object) -> None:
        _ = event, kw

    def info(self, event: str, **kw: object) -> None:
        _ = event, kw

    def warning(self, event: str, **kw: object) -> None:
        _ = event, kw

    def error(self, event: str, **kw: object) -> None:
        _ = event, kw

    def exception(self, event: str, **kw: object) -> None:
        _ = event, kw


@pytest.fixture()
def recognizer() -> BattleMedalRecognizerAdapter:
    return BattleMedalRecognizerAdapter(cast(LoggerPort, _DummyLogger()))


@pytest.fixture()
def load_image() -> Callable[[str], np.ndarray]:
    def _load(filename: str) -> np.ndarray:
        image = cv2.imread(str(TEMPLATE_DIR / filename))
        if image is None:
            pytest.skip(f"画像読み込み失敗: {filename}")
        return image

    return _load


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("battle_result_2.png", (0, 0)),
        ("battle_result_10.png", (2, 1)),
        ("battle_result_11.png", (3, 0)),
        ("battle_result_14.png", (0, 3)),
        ("battle_result_17.png", (1, 2)),
        ("battle_result_19.png", (2, 0)),
    ],
)
async def test_count_medals(
    recognizer: BattleMedalRecognizerAdapter,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: tuple[int, int],
) -> None:
    frame = as_frame(load_image(filename))
    assert await recognizer.count_medals(frame) == expected
