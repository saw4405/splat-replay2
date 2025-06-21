"""画像処理ユーティリティ。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Dict
from abc import ABC, abstractmethod
import hashlib

import cv2
import numpy as np

from splat_replay.shared.config import ImageMatchingSettings


def load_image(path: str, *, grayscale: bool = False) -> Optional[np.ndarray]:
    """画像を読み込む。

    :param path: 画像ファイルのパス
    :param grayscale: グレースケールで読み込むかどうか
    :return: 読み込んだ ``ndarray``、失敗した場合 ``None``
    """

    flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    return cv2.imread(str(Path(path)), flag)


def match_template(
    image: np.ndarray,
    template: np.ndarray,
    *,
    method: int = cv2.TM_CCOEFF_NORMED,
) -> float:
    """テンプレートマッチングを行う。

    :param image: 入力画像
    :param template: テンプレート画像
    :param method: OpenCV のマッチング手法
    :return: 最大マッチングスコア
    """

    result = cv2.matchTemplate(image, template, method)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return float(max_val)


def calculate_brightness(image: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
    """画像の平均明度を計算するユーティリティ。"""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if mask is not None:
        pixels = gray[mask == 255]
    else:
        pixels = gray.flatten()
    if pixels.size == 0:
        return 0.0
    return float(np.mean(pixels))


class BaseMatcher(ABC):
    """画像マッチングの基底クラス。"""

    def __init__(
        self,
        mask_path: Optional[str] = None,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> None:
        self._mask = (
            cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE) if mask_path else None
        )
        if mask_path and self._mask is None:
            raise ValueError(f"マスク画像の読み込みに失敗しました: {mask_path}")
        self._roi = roi

    def _apply_roi(self, image: np.ndarray) -> np.ndarray:
        if self._roi is None:
            return image
        x, y, w, h = self._roi
        return image[y : y + h, x : x + w]

    @abstractmethod
    def match(self, image: np.ndarray) -> bool:
        """画像が条件に一致するか判定する。"""


class HashMatcher(BaseMatcher):
    """ハッシュ値による完全一致判定用マッチャー。"""

    def __init__(self, image_path: str, roi: Optional[Tuple[int, int, int, int]] = None) -> None:
        super().__init__(None, roi)
        self._hash_value = self._compute_hash(cv2.imread(image_path))

    def _compute_hash(self, image: np.ndarray) -> str:
        return hashlib.sha1(image).hexdigest()

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        image_hash = self._compute_hash(img)
        return image_hash == self._hash_value


class HSVMatcher(BaseMatcher):
    """HSV 色空間で色域一致を判定するマッチャー。"""

    def __init__(
        self,
        lower_bound: Tuple[int, int, int],
        upper_bound: Tuple[int, int, int],
        mask_path: Optional[str] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> None:
        super().__init__(mask_path, roi)
        self._lower_bound = np.array(lower_bound, dtype=np.uint8)
        self._upper_bound = np.array(upper_bound, dtype=np.uint8)
        self._threshold = threshold

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        if self._mask is not None:
            masked = cv2.bitwise_and(img, img, mask=self._mask)
        else:
            masked = img

        hsv = cv2.cvtColor(masked, cv2.COLOR_BGR2HSV)
        color_mask = cv2.inRange(hsv, self._lower_bound, self._upper_bound)

        if self._mask is not None:
            combined = cv2.bitwise_and(color_mask, color_mask, mask=self._mask)
            total = cv2.countNonZero(self._mask)
            count = cv2.countNonZero(combined)
        else:
            total = img.shape[0] * img.shape[1]
            count = cv2.countNonZero(color_mask)

        ratio = count / total if total > 0 else 0
        return ratio >= self._threshold


class UniformColorMatcher(BaseMatcher):
    """画像全体が同系色かを判定するマッチャー。"""

    def __init__(
        self,
        mask_path: Optional[str] = None,
        hue_threshold: float = 10.0,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> None:
        super().__init__(mask_path, roi)
        self._hue_threshold = hue_threshold

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0]
        if self._mask is not None:
            values = hue[self._mask == 255]
        else:
            values = hue.flatten()

        if values.size == 0:
            return False

        std_hue = np.std(values.astype(np.float32))
        return bool(std_hue <= self._hue_threshold)


class RGBMatcher(BaseMatcher):
    """RGB 値の一致を判定するマッチャー。"""

    def __init__(
        self,
        rgb: Tuple[int, int, int],
        mask_path: Optional[str] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> None:
        super().__init__(mask_path, roi)
        self._rgb = rgb
        self._threshold = threshold

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        if self._mask is not None:
            mask = self._mask == 255
            masked = img[mask]
            total = int(np.sum(mask))
        else:
            masked = img.reshape(-1, 3)
            total = img.shape[0] * img.shape[1]

        match_pixels = np.all(masked == self._rgb, axis=-1)
        match_count = int(np.sum(match_pixels))
        if total == 0:
            return False
        ratio = match_count / total
        return ratio >= self._threshold


class TemplateMatcher(BaseMatcher):
    """テンプレートマッチングを行うマッチャー。"""

    def __init__(
        self,
        template_path: str,
        mask_path: Optional[str] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> None:
        super().__init__(mask_path, roi)
        template = cv2.imread(template_path)
        if template is None:
            raise ValueError(f"テンプレート画像の読み込みに失敗しました: {template_path}")
        self._template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        self._threshold = threshold

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if self._mask is not None:
            result = cv2.matchTemplate(gray, self._template, cv2.TM_CCOEFF_NORMED, mask=self._mask)
        else:
            result = cv2.matchTemplate(gray, self._template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= self._threshold


class BrightnessMatcher(BaseMatcher):
    """平均明度が閾値内か判定するマッチャー。"""

    def __init__(
        self,
        max_value: Optional[float] = None,
        min_value: Optional[float] = None,
        mask_path: Optional[str] = None,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> None:
        super().__init__(mask_path, roi)
        self._max_value = max_value
        self._min_value = min_value

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        level = calculate_brightness(img, self._mask)
        if self._max_value is not None and level > self._max_value:
            return False
        if self._min_value is not None and level < self._min_value:
            return False
        return True


class CompositeMatcher:
    """複数のマッチャー結果をまとめて評価するクラス。"""

    def __init__(
        self,
        matchers: list[BaseMatcher],
        policy: str = "any_can_pass",
        min_required: int = 1,
    ) -> None:
        self.matchers = matchers
        self.policy = policy
        self.min_required = min_required

    def match(self, image: np.ndarray) -> bool:
        """設定されたポリシーに基づき判定する。"""
        results = [m.match(image) for m in self.matchers]
        if self.policy == "all_must_pass":
            return all(results)
        if self.policy == "majority_pass":
            required = max(self.min_required, 1)
            return sum(results) >= required
        # any_can_pass がデフォルト
        return any(results)


def build_matcher(config: "MatcherConfig") -> Optional[BaseMatcher]:
    """設定からマッチャーインスタンスを生成する。"""

    if not config:
        return None

    mask_path = getattr(config, "mask_path", None)
    roi_cfg = getattr(config, "roi", None)
    roi = None
    if roi_cfg:
        roi = (
            int(roi_cfg.get("x", 0)),
            int(roi_cfg.get("y", 0)),
            int(roi_cfg.get("width", 0)),
            int(roi_cfg.get("height", 0)),
        )
    if config.type == "hash" and config.template_path:
        try:
            return HashMatcher(config.template_path, roi)
        except Exception:
            return None
    if config.type == "hsv" and config.lower_bound and config.upper_bound:
        return HSVMatcher(
            tuple(config.lower_bound),
            tuple(config.upper_bound),
            mask_path,
            config.threshold,
            roi,
        )
    if config.type == "rgb" and config.rgb:
        return RGBMatcher(tuple(config.rgb), mask_path, config.threshold, roi)
    if config.type == "uniform":
        return UniformColorMatcher(mask_path, config.hue_threshold or 10.0, roi)
    if config.type == "brightness" and (
        config.max_value is not None or config.min_value is not None
    ):
        return BrightnessMatcher(
            config.max_value,
            config.min_value,
            mask_path,
            roi,
        )
    if config.type == "template" and config.template_path:
        try:
            return TemplateMatcher(
                config.template_path,
                mask_path,
                config.threshold,
                roi,
            )
        except Exception:
            return None
    return None


def build_composite_matcher(
    config: "CompositeMatcherConfig", lookup: dict[str, BaseMatcher]
) -> Optional[CompositeMatcher]:
    """設定から複合マッチャーを生成する。"""

    matchers: list[BaseMatcher] = []
    for name in config.matchers:
        m = lookup.get(name)
        if m:
            matchers.append(m)

    if not matchers:
        return None

    return CompositeMatcher(matchers, config.success_condition, config.min_required_steps)


class MatcherRegistry:
    """設定に基づいてマッチャーを管理するクラス。"""

    def __init__(self, settings: "ImageMatchingSettings") -> None:
        # 単体マッチャーの登録
        self.matchers: Dict[str, BaseMatcher] = {}
        for name, cfg in settings.matchers.items():
            matcher = build_matcher(cfg)
            if matcher:
                self.matchers[name] = matcher

        # 複合マッチャーの登録
        self.composites: Dict[str, CompositeMatcher] = {}
        for name, comp in settings.composites.items():
            composite = build_composite_matcher(comp, self.matchers)
            if composite:
                self.composites[name] = composite

    def match(self, key: str, image: np.ndarray) -> bool:
        """指定されたキーのマッチャーで判定する。"""

        matcher = self.composites.get(key)
        if matcher is None:
            matcher = self.matchers.get(key)
        return matcher.match(image) if matcher else False
