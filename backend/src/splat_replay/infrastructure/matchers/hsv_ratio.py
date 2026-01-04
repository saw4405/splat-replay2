import asyncio
from typing import Optional, Tuple

import cv2
import numpy as np

from .base import BaseMatcher


class HSVRatioMatcher(BaseMatcher):
    """画像全体に対するHSV色域の占有率で判定するマッチャー。"""

    def __init__(
        self,
        lower_bound: Tuple[int, int, int],
        upper_bound: Tuple[int, int, int],
        threshold: float = 0.5,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(None, roi, name)
        self._lower_bound = np.array(lower_bound, dtype=np.uint8)
        self._upper_bound = np.array(upper_bound, dtype=np.uint8)
        self._threshold = threshold

    async def match(self, image: np.ndarray) -> bool:
        return await asyncio.to_thread(self._match, image)

    def _match(self, image: np.ndarray) -> bool:
        # Apply ROI first
        img = self._apply_roi(image)
        # Lightweight downsampling to reduce work (~4x fewer pixels)
        # Keeps ratio characteristics stable for thresholding use-cases.
        img_small = img[::2, ::2]
        hsv = cv2.cvtColor(img_small, cv2.COLOR_BGR2HSV)
        color_mask = cv2.inRange(hsv, self._lower_bound, self._upper_bound)
        total = img_small.shape[0] * img_small.shape[1]
        count = cv2.countNonZero(color_mask)
        ratio = count / total if total > 0 else 0.0
        return bool(ratio >= self._threshold)
