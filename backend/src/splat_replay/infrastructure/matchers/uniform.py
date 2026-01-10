import asyncio
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .base import BaseMatcher


class UniformColorMatcher(BaseMatcher):
    """画像全体が同系色かを判定するマッチャー。"""

    def __init__(
        self,
        mask_path: Optional[Path] = None,
        hue_threshold: float = 10.0,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
        self._hue_threshold = hue_threshold

    async def match(self, image: np.ndarray) -> bool:
        return await asyncio.to_thread(self._match, image)

    def _match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0]
        if self._mask is not None:
            values = hue[self._mask == 255]
        else:
            values = hue.flatten()

        if values.size == 0:
            return False

        # 赤色（Hue が 0 付近と 180 付近）を考慮した均一性判定
        # 色相環は円形（0 と 180 が隣接）なので、通常の標準偏差では赤色を正しく判定できない
        result = self._is_uniform_hue(values, self._hue_threshold)
        return result

    def _is_uniform_hue(
        self, hue_values: np.ndarray, threshold: float
    ) -> bool:
        """色相の均一性を円形色相を考慮して判定する。

        Args:
            hue_values: Hue 値の配列 (0-180)
            threshold: 均一と判定する閾値

        Returns:
            True if 色相が均一, False otherwise

        Note:
            HSV の Hue は 0-180 の範囲で、0 と 180 が隣接する円形色相。
            赤色は Hue 0 付近と 180 付近に分かれるため、特別な処理が必要。
        """
        # 標準偏差による判定（通常ケース）
        std_hue = float(np.std(hue_values.astype(np.float32)))
        if std_hue <= threshold:
            return True

        # 赤色の可能性がある場合は円形距離で再判定
        # Hue の範囲が広い（両端に分かれている可能性）場合のみチェック
        hue_range = float(np.max(hue_values) - np.min(hue_values))
        if hue_range <= threshold * 2:
            # 範囲が狭ければ既に標準偏差で判定済み
            return False

        # 円形距離を計算（Hue を 2倍して sin/cos で変換し、平均ベクトルとの角度差を計算）
        # これにより 0 と 180 が隣接していることを考慮できる
        hue_rad = hue_values.astype(np.float32) * 2.0 * np.pi / 180.0
        mean_x = float(np.mean(np.cos(hue_rad)))
        mean_y = float(np.mean(np.sin(hue_rad)))
        mean_angle = np.arctan2(mean_y, mean_x)

        # 各ピクセルと平均角度の円形距離を計算
        angular_distances = np.abs(
            np.arctan2(
                np.sin(hue_rad - mean_angle), np.cos(hue_rad - mean_angle)
            )
        )
        circular_std = float(np.std(angular_distances) * 180.0 / (2.0 * np.pi))

        return circular_std <= threshold
