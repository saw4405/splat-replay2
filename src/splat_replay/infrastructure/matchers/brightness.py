from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import cv2
from .base import BaseMatcher
from structlog.stdlib import BoundLogger


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
        logger: BoundLogger,
    ) -> None:
        super().__init__(mask_path, roi, name)
        self.logger = logger
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

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        level = self._calculate_brightness(img, self._mask)
        if self._max_value is not None and level > self._max_value:
            self.logger.debug(
                "明度上限超過", level=float(level), max=self._max_value
            )
            return False
        if self._min_value is not None and level < self._min_value:
            self.logger.debug(
                "明度下限未満", level=float(level), min=self._min_value
            )
            return False
        return True
