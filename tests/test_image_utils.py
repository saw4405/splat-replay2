import numpy as np
from pathlib import Path

from splat_replay.infrastructure.analyzers.common.image_utils import (
    RGBMatcher,
    BrightnessMatcher,
)


def test_rgb_matcher_roi() -> None:
    img = np.zeros((4, 4, 3), dtype=np.uint8)
    img[:, :2] = (255, 0, 0)
    m_no_roi = RGBMatcher((255, 0, 0), threshold=0.75)
    assert not m_no_roi.match(img)
    m_roi = RGBMatcher((255, 0, 0), threshold=0.75, roi=(0, 0, 2, 4))
    assert m_roi.match(img)


def test_brightness_matcher_min_max(tmp_path: Path) -> None:
    img = np.full((2, 2, 3), 255, dtype=np.uint8)
    m = BrightnessMatcher(min_value=200)
    assert m.match(img)
    m2 = BrightnessMatcher(max_value=100)
    assert not m2.match(img)

