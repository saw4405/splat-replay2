from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
from abc import ABC, abstractmethod
import cv2
import numpy as np


class BaseMatcher(ABC):
    """画像マッチングの基底クラス。"""

    def __init__(
        self,
        mask_path: Optional[Path] = None,
        roi: Optional[Tuple[int, int, int, int]] = None,
        name: str | None = None,
    ) -> None:
        self.name = name
        self._mask = (
            cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask_path
            else None
        )
        self._roi = roi

    def _apply_roi(self, image: np.ndarray) -> np.ndarray:
        if self._roi is None:
            return image
        x, y, w, h = self._roi
        return image[y : y + h, x : x + w]

    @abstractmethod
    def match(self, image: np.ndarray) -> bool:
        """画像が条件に一致するか判定する。"""
