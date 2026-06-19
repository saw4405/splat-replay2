"""画像編集ユーティリティクラス。"""

import cv2
import numpy as np

from splat_replay.domain.models import Frame, as_frame
from splat_replay.domain.ports import ImageEditorPort


class ImageEditor(ImageEditorPort):
    """画像編集ユーティリティ（メソッドチェーン対応）。"""

    def __init__(self, image: Frame):
        self._image = image

    @property
    def image(self) -> Frame:
        return self._image

    def rotate(self, angle: float) -> "ImageEditor":
        rows, cols = self._image.shape[:2]
        M = cv2.getRotationMatrix2D((cols / 2, rows / 2), angle, 1)
        image = cv2.warpAffine(self._image, M, (cols, rows))
        self._image = as_frame(image)
        return self

    def resize(self, scale_x: float, scale_y: float) -> "ImageEditor":
        image = cv2.resize(self._image, (0, 0), fx=scale_x, fy=scale_y)
        self._image = as_frame(image)
        return self

    def padding(
        self,
        top: int,
        bottom: int,
        left: int,
        right: int,
        color: tuple[int, int, int] = (255, 255, 255),
    ) -> "ImageEditor":
        image = cv2.copyMakeBorder(
            self._image,
            top,
            bottom,
            left,
            right,
            cv2.BORDER_CONSTANT,
            value=color,
        )
        self._image = as_frame(image)
        return self

    def binarize(self, threshold: int | None = None) -> "ImageEditor":
        gray_image = cv2.cvtColor(self._image, cv2.COLOR_BGR2GRAY)
        threshold_value = 0 if threshold is None else threshold
        threshold_type = cv2.THRESH_BINARY
        if threshold is None:
            threshold_type += cv2.THRESH_OTSU
        image = cv2.threshold(
            gray_image, threshold_value, 255, threshold_type
        )[1]
        self._image = as_frame(image)
        return self

    def erode(
        self, kernel_size: tuple[int, int] = (2, 2), iterations: int = 1
    ) -> "ImageEditor":
        kernel = np.ones(kernel_size, np.uint8)
        image = cv2.erode(self._image, kernel, iterations=iterations)
        self._image = as_frame(image)
        return self

    def invert(self) -> "ImageEditor":
        image = cv2.bitwise_not(self._image)
        self._image = as_frame(image)
        return self

    def count_connected_components(
        self, *, foreground_threshold: int, min_area: int
    ) -> int:
        if self._image.ndim == 3:
            gray_image = cv2.cvtColor(self._image, cv2.COLOR_BGR2GRAY)
        else:
            gray_image = self._image
        foreground = (gray_image < foreground_threshold).astype(np.uint8)
        count, _, stats, _ = cv2.connectedComponentsWithStats(
            foreground, connectivity=8
        )
        return sum(
            1
            for index in range(1, count)
            if int(stats[index, cv2.CC_STAT_AREA]) >= min_area
        )
