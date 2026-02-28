import asyncio
from pathlib import Path
from typing import Callable, Optional, Tuple

import cv2
import numpy as np

from .base import BaseMatcher
from .utils import imread_unicode


class TemplateMatcher(BaseMatcher):
    """テンプレートマッチングを行うマッチャー。"""

    def __init__(
        self,
        template_path: Path,
        mask_path: Optional[Path] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
        response_top_k: int = 1,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
        if response_top_k < 1:
            raise ValueError("response_top_k は 1 以上である必要があります")
        self.template_path = template_path
        self.mask_path = mask_path
        template = imread_unicode(template_path)
        if template is None:
            raise FileNotFoundError(
                f"テンプレート画像の読み込みに失敗しました: {template_path}"
            )
        self._template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        self._threshold = threshold
        self._response_top_k = response_top_k

    async def match(self, image: np.ndarray) -> bool:
        return await asyncio.to_thread(self._match, image)

    def _match(self, image: np.ndarray) -> bool:
        return self._score(image) >= self._threshold

    async def score(
        self,
        image: np.ndarray,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> float:
        """テンプレート一致スコアを返す。"""
        return await asyncio.to_thread(self._score, image, cancel_check)

    def _score(
        self,
        image: np.ndarray,
        cancel_check: Callable[[], bool] | None = None,
    ) -> float:
        if cancel_check is not None and cancel_check():
            raise asyncio.CancelledError("template scoring cancelled")
        img = self._apply_roi(image)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if cancel_check is not None and cancel_check():
            raise asyncio.CancelledError("template scoring cancelled")
        if self._mask is not None:
            result = cv2.matchTemplate(
                gray, self._template, cv2.TM_CCOEFF_NORMED, mask=self._mask
            )
        else:
            result = cv2.matchTemplate(
                gray, self._template, cv2.TM_CCOEFF_NORMED
            )
        if cancel_check is not None and cancel_check():
            raise asyncio.CancelledError("template scoring cancelled")

        return self._aggregate_match_response(result)

    def _aggregate_match_response(self, result: np.ndarray) -> float:
        finite_mask = np.isfinite(result)
        if not np.any(finite_mask):
            return -1.0
        values = result[finite_mask].astype(np.float32, copy=False).ravel()
        if values.size == 0:
            return -1.0
        if self._response_top_k == 1 or values.size == 1:
            return float(np.max(values))

        top_k = min(self._response_top_k, int(values.size))
        top_indices = np.argpartition(values, -top_k)[-top_k:]
        top_values = values[top_indices]
        return float(np.mean(top_values))
