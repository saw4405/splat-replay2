import asyncio
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .base import BaseMatcher


class UniformColorMatcher(BaseMatcher):
    """画像全体が同系色かを判定するマッチャー。"""

    def __init__(
        self,
        mask_path: Optional[Path] = None,
        hue_threshold: float = 10.0,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
        self._hue_threshold = hue_threshold

    async def match(self, image: np.ndarray) -> bool:
        return await asyncio.to_thread(self._match, image)

    def _match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0]
        if self._mask is not None:
            values = hue[self._mask == 255]
        else:
            values = hue.flatten()

        if values.size == 0:
            return False

        std_hue = np.std(values.astype(np.float32))
        result = bool(std_hue <= self._hue_threshold)
        return result
