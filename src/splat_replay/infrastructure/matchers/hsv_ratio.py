from typing import Optional, Tuple
import numpy as np
import cv2
from .base import BaseMatcher
from splat_replay.shared.logger import get_logger

logger = get_logger()


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

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        color_mask = cv2.inRange(hsv, self._lower_bound, self._upper_bound)
        total = img.shape[0] * img.shape[1]
        count = cv2.countNonZero(color_mask)
        ratio = count / total if total > 0 else 0
        result = ratio >= self._threshold
        if not result:
            logger.debug(
                "HSV占有率不足",
                ratio=float(ratio),
                threshold=self._threshold,
            )
        return result
