from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .base import BaseMatcher

class EdgeMatcher(BaseMatcher):
    def __init__(
        self,
        template_path: Path,
        threshold: float = 2000,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(None, roi, name)
        template = cv2.imread(str(template_path))
        if template is None:
            raise ValueError(f"テンプレート画像が読み込めません: {template_path}")
        self._template_edge = self._canny(template)
        self._threshold = threshold

    def match(self, image: np.ndarray) -> bool:
        frame = self._apply_roi(image)
        edge = self._canny(frame)
        dist = cv2.distanceTransform(255 - edge, cv2.DIST_L2, 3)
        res = cv2.filter2D(dist, -1, self._template_edge.astype(np.float32) / 255.0)
        min_val, _, _, _ = cv2.minMaxLoc(res)
        return min_val <= self._threshold

    def _canny(self, bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        return cv2.Canny(blur, 50, 150)