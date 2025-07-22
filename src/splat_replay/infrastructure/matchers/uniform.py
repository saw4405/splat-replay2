from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import cv2
from .base import BaseMatcher
from splat_replay.shared.logger import get_logger

logger = get_logger()


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

    def match(self, image: np.ndarray) -> bool:
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
        if not result:
            logger.debug(
                "色相分散大", std=float(std_hue), threshold=self._hue_threshold
            )
        return result
