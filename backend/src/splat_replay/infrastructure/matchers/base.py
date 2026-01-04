from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .utils import imread_unicode


class BaseMatcher(ABC):
    """画像マッチングの基底クラス。"""

    def __init__(
        self,
        mask_path: Optional[Path] = None,
        roi: Optional[Tuple[int, int, int, int]] = None,
        name: str | None = None,
    ) -> None:
        self.name = name
        self._mask: Optional[np.ndarray] = None
        if mask_path is not None:
            mask = imread_unicode(mask_path, cv2.IMREAD_GRAYSCALE)
            if mask is None:
                raise FileNotFoundError(
                    f"マスク画像の読み込みに失敗しました: {mask_path}"
                )
            self._mask = mask
        self._roi = roi

    def _apply_roi(self, image: np.ndarray) -> np.ndarray:
        if self._roi is None:
            return image
        x, y, w, h = self._roi
        return image[y : y + h, x : x + w]

    @abstractmethod
    async def match(self, image: np.ndarray) -> bool:
        """画像が条件に一致するか判定する。"""
