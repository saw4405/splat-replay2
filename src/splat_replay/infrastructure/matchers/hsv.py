from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np
from .base import BaseMatcher
from splat_replay.shared.logger import get_logger

logger = get_logger()


class HSVMatcher(BaseMatcher):
    """HSV 色空間で色域一致を判定するマッチャー。"""

    def __init__(
        self,
        lower_bound: Tuple[int, int, int],
        upper_bound: Tuple[int, int, int],
        mask_path: Optional[Path] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
        self._lower_bound = np.array(lower_bound, dtype=np.uint8)
        self._upper_bound = np.array(upper_bound, dtype=np.uint8)
        self._threshold = threshold

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        if self._mask is not None:
            masked = cv2.bitwise_and(img, img, mask=self._mask)
        else:
            masked = img

        hsv = cv2.cvtColor(masked, cv2.COLOR_BGR2HSV)
        color_mask = cv2.inRange(hsv, self._lower_bound, self._upper_bound)

        if self._mask is not None:
            combined = cv2.bitwise_and(color_mask, color_mask, mask=self._mask)
            total = cv2.countNonZero(self._mask)
            count = cv2.countNonZero(combined)
        else:
            total = img.shape[0] * img.shape[1]
            count = cv2.countNonZero(color_mask)

        ratio = count / total if total > 0 else 0
        result = ratio >= self._threshold
        if not result:
            logger.debug(
                "HSV 比率不足",
                ratio=float(ratio),
                threshold=self._threshold,
            )
        return result
