import asyncio
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .base import BaseMatcher


class BrightnessMatcher(BaseMatcher):
    """最大明度が閾値内か判定するマッチャー。"""

    def __init__(
        self,
        max_value: Optional[float] = None,
        min_value: Optional[float] = None,
        mask_path: Optional[Path] = None,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
        self._max_value = max_value
        self._min_value = min_value

    def _calculate_brightness(
        self, image: np.ndarray, mask: Optional[np.ndarray] = None
    ) -> float:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if mask is not None:
            pixels = gray[mask == 255]
        else:
            pixels = gray.flatten()
        if pixels.size == 0:
            return 0.0
        return float(np.max(pixels))

    async def match(self, image: np.ndarray) -> bool:
        return await asyncio.to_thread(self._match, image)

    def _match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        level = self._calculate_brightness(img, self._mask)
        if self._max_value is not None and level > self._max_value:
            return False
        if self._min_value is not None and level < self._min_value:
            return False
        return True
