from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))  # noqa: E402

from splat_replay.infrastructure.analyzers.common.image_utils import (  # noqa: E402
    MatcherRegistry,
)
from splat_replay.shared.config import ImageMatchingSettings  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
MATCHER_SETTINGS = ImageMatchingSettings.load_from_yaml(
    BASE_DIR.parent / "config" / "image_matching.yaml"
)
TEMPLATE_DIR = BASE_DIR / "fixtures" / "templates"


@pytest.fixture()
def registry() -> MatcherRegistry:
    return MatcherRegistry(MATCHER_SETTINGS)


def test_matcher_has_name(registry: MatcherRegistry) -> None:
    matcher = registry.matchers.get("battle_start") or registry.composites.get(
        "battle_start"
    )
    assert matcher is not None
    assert matcher.name == "battle_start"


@pytest.fixture()
def load_image() -> Callable[[str], np.ndarray]:
    def _load(filename: str) -> np.ndarray:
        path = TEMPLATE_DIR / filename
        image = cv2.imread(str(path))
        if image is None:
            pytest.skip(f"画像ファイルが存在しないか読み込めません: {path}")
        return image

    return _load


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_start_1.png", "battle_start"),
        ("battle_abort_1.png", "battle_abort"),
        ("matching_1.png", None),
    ],
)
def test_match_first(
    registry: MatcherRegistry,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: str | None,
) -> None:
    frame = load_image(filename)
    result = registry.match_first(["battle_start", "battle_abort"], frame)
    assert result == expected
    if result is not None:
        matcher = registry.matchers.get(result) or registry.composites.get(
            result
        )
        assert matcher is not None
        assert matcher.name == result
