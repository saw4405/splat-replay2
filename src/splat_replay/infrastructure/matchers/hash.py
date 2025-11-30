import asyncio
import hashlib
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from .base import BaseMatcher
from .utils import imread_unicode


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
        loaded_image = imread_unicode(image_path)
        if loaded_image is None:
            raise FileNotFoundError(
                f"画像ファイルの読み込みに失敗しました: {image_path}"
            )
        self._hash_value = self._compute_hash(loaded_image)

    def _compute_hash(self, image: np.ndarray) -> str:
        return hashlib.sha1(image.tobytes()).hexdigest()

    async def match(self, image: np.ndarray) -> bool:
        return await asyncio.to_thread(self._match, image)

    def _match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        image_hash = self._compute_hash(img)
        result = image_hash == self._hash_value
        return result
