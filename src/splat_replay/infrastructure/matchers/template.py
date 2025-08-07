from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .base import BaseMatcher


class TemplateMatcher(BaseMatcher):
    """テンプレートマッチングを行うマッチャー。"""

    def __init__(
        self,
        template_path: Path,
        mask_path: Optional[Path] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
        template = cv2.imread(str(template_path))
        if template is None:
            raise ValueError(
                f"テンプレート画像の読み込みに失敗しました: {template_path}"
            )
        self._template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        self._threshold = threshold

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if self._mask is not None:
            result = cv2.matchTemplate(
                gray, self._template, cv2.TM_CCOEFF_NORMED, mask=self._mask
            )
        else:
            result = cv2.matchTemplate(
                gray, self._template, cv2.TM_CCOEFF_NORMED
            )

        _, max_val, _, _ = cv2.minMaxLoc(result)
        return  max_val >= self._threshold