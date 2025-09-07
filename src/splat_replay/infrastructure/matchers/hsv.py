import asyncio
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .base import BaseMatcher


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
        # When a large full-frame mask is provided without ROI, precompute
        # the mask's bounding box to reduce the processing area.
        self._mask_bbox: Optional[Tuple[int, int, int, int]] = None
        if self._roi is None and self._mask is not None:
            nz = cv2.findNonZero(self._mask)
            if nz is not None:
                x, y, w, h = cv2.boundingRect(nz)
                self._mask_bbox = (int(x), int(y), int(w), int(h))

    async def match(self, image: np.ndarray) -> bool:
        return await asyncio.to_thread(self._match, image)

    def _match(self, image: np.ndarray) -> bool:
        # Decide processing region and corresponding mask to minimize work.
        roi_to_use: Optional[Tuple[int, int, int, int]]
        mask_to_use: Optional[np.ndarray]

        if self._roi is not None:
            # Use explicitly provided ROI; crop mask to ROI if present
            x, y, w, h = self._roi
            roi_to_use = (x, y, w, h)
            mask_to_use = (
                self._mask[y : y + h, x : x + w]
                if self._mask is not None
                else None
            )
        elif self._mask_bbox is not None and self._mask is not None:
            # No ROI, but mask has a tight bounding box
            x, y, w, h = self._mask_bbox
            roi_to_use = (x, y, w, h)
            mask_to_use = self._mask[y : y + h, x : x + w]
        else:
            roi_to_use = None
            mask_to_use = self._mask

        if roi_to_use is not None:
            x, y, w, h = roi_to_use
            img = image[y : y + h, x : x + w]
        else:
            img = image

        # Compute HSV only on the necessary area, with light downsampling to
        # reduce work while keeping ratios stable.
        # Downsample by a factor of 2 if region is reasonably large.
        if img.shape[0] >= 60 and img.shape[1] >= 60:
            img_small = img[::2, ::2]
            mask_small = (
                mask_to_use[::2, ::2] if mask_to_use is not None else None
            )
        else:
            img_small = img
            mask_small = mask_to_use

        hsv = cv2.cvtColor(img_small, cv2.COLOR_BGR2HSV)
        color_mask = cv2.inRange(hsv, self._lower_bound, self._upper_bound)

        if mask_small is not None:
            # Count only within mask area
            combined = cv2.bitwise_and(color_mask, color_mask, mask=mask_small)
            total = cv2.countNonZero(mask_small)
            count = cv2.countNonZero(combined)
        else:
            total = img_small.shape[0] * img_small.shape[1]
            count = cv2.countNonZero(color_mask)

        ratio = count / total if total > 0 else 0.0
        return bool(ratio >= self._threshold)
