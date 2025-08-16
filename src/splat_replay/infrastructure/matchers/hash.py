import asyncio
import hashlib
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .base import BaseMatcher


class HashMatcher(BaseMatcher):
    """ハッシュ値による完全一致判定用マッチャー。"""

    def __init__(
        self,
        image_path: Path,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(None, roi, name)
        self._hash_value = self._compute_hash(cv2.imread(str(image_path)))

    def _compute_hash(self, image: np.ndarray) -> str:
        return hashlib.sha1(image).hexdigest()

    async def match(self, image: np.ndarray) -> bool:
        return await asyncio.to_thread(self._match, image)

    def _match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        image_hash = self._compute_hash(img)
        result = image_hash == self._hash_value
        return result
