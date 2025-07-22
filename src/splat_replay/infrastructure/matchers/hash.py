from pathlib import Path
from typing import Optional, Tuple
import hashlib
import cv2
import numpy as np
from .base import BaseMatcher
from splat_replay.shared.logger import get_logger

logger = get_logger()


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

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        image_hash = self._compute_hash(img)
        result = image_hash == self._hash_value
        if not result:
            logger.debug(
                "ハッシュ不一致",
                expected=self._hash_value,
                actual=image_hash,
            )
        return result
