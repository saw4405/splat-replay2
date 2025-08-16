import asyncio
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from .base import BaseMatcher


class RGBMatcher(BaseMatcher):
    """RGB 値の一致を判定するマッチャー。"""

    def __init__(
        self,
        rgb: Tuple[int, int, int],
        mask_path: Optional[Path] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
        self._rgb = rgb
        self._threshold = threshold

    async def match(self, image: np.ndarray) -> bool:
        return await asyncio.to_thread(self._match, image)

    def _match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        if self._mask is not None:
            mask = self._mask == 255
            masked = img[mask]
            total = int(np.sum(mask))
        else:
            masked = img.reshape(-1, 3)
            total = img.shape[0] * img.shape[1]

        match_pixels = np.all(masked == self._rgb, axis=-1)
        match_count = int(np.sum(match_pixels))
        if total == 0:
            return False
        ratio = match_count / total
        result = ratio >= self._threshold
        return result
