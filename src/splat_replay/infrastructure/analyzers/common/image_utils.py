"""画像処理ユーティリティ。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Dict
from abc import ABC, abstractmethod
import hashlib

import cv2
import numpy as np

from splat_replay.shared.config import (
    ImageMatchingSettings,
    MatcherConfig,
    CompositeMatcherConfig,
)
from splat_replay.domain.models import MatchExpression
from splat_replay.shared.logger import get_logger

logger = get_logger()


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


def calculate_brightness(
    image: np.ndarray, mask: Optional[np.ndarray] = None
) -> float:
    """画像の最大明度を計算するユーティリティ。"""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if mask is not None:
        pixels = gray[mask == 255]
    else:
        pixels = gray.flatten()
    if pixels.size == 0:
        return 0.0
    return float(np.max(pixels))


class BaseMatcher(ABC):
    """画像マッチングの基底クラス。"""

    def __init__(
        self,
        mask_path: Optional[str] = None,
        roi: Optional[Tuple[int, int, int, int]] = None,
        name: str | None = None,
    ) -> None:
        """マッチャーを初期化する。"""

        self.name = name
        self._mask = (
            cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE) if mask_path else None
        )
        # マスクが読み込めなくても None として続行する
        self._roi = roi

    def _apply_roi(self, image: np.ndarray) -> np.ndarray:
        if self._roi is None:
            return image
        x, y, w, h = self._roi
        return image[y: y + h, x: x + w]

    @abstractmethod
    def match(self, image: np.ndarray) -> bool:
        """画像が条件に一致するか判定する。"""


class HashMatcher(BaseMatcher):
    """ハッシュ値による完全一致判定用マッチャー。"""

    def __init__(
        self,
        image_path: str,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(None, roi, name)
        self._hash_value = self._compute_hash(cv2.imread(image_path))

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


class HSVMatcher(BaseMatcher):
    """HSV 色空間で色域一致を判定するマッチャー。"""

    def __init__(
        self,
        lower_bound: Tuple[int, int, int],
        upper_bound: Tuple[int, int, int],
        mask_path: Optional[str] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
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
        result = ratio >= self._threshold
        if not result:
            logger.debug(
                "HSV 比率不足",
                ratio=float(ratio),
                threshold=self._threshold,
            )
        return result


class UniformColorMatcher(BaseMatcher):
    """画像全体が同系色かを判定するマッチャー。"""

    def __init__(
        self,
        mask_path: Optional[str] = None,
        hue_threshold: float = 10.0,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
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
        result = bool(std_hue <= self._hue_threshold)
        if not result:
            logger.debug(
                "色相分散大", std=float(std_hue), threshold=self._hue_threshold
            )
        return result


class RGBMatcher(BaseMatcher):
    """RGB 値の一致を判定するマッチャー。"""

    def __init__(
        self,
        rgb: Tuple[int, int, int],
        mask_path: Optional[str] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
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
        result = ratio >= self._threshold
        if not result:
            logger.debug(
                "RGB 比率不足", ratio=float(ratio), threshold=self._threshold
            )
        return result


class TemplateMatcher(BaseMatcher):
    """テンプレートマッチングを行うマッチャー。"""

    def __init__(
        self,
        template_path: str,
        mask_path: Optional[str] = None,
        threshold: float = 0.9,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
        template = cv2.imread(template_path)
        if template is None:
            raise ValueError(
                f"テンプレート画像の読み込みに失敗しました: {template_path}"
            )
        self._template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        self._threshold = threshold

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if self._mask is not None:
            result = cv2.matchTemplate(
                gray, self._template, cv2.TM_CCOEFF_NORMED, mask=self._mask
            )
        else:
            result = cv2.matchTemplate(
                gray, self._template, cv2.TM_CCOEFF_NORMED
            )
        _, max_val, _, _ = cv2.minMaxLoc(result)
        result_flag = max_val >= self._threshold
        if not result_flag:
            logger.debug(
                "テンプレート不一致",
                score=float(max_val),
                threshold=self._threshold,
            )
        return result_flag


class BrightnessMatcher(BaseMatcher):
    """最大明度が閾値内か判定するマッチャー。"""

    def __init__(
        self,
        max_value: Optional[float] = None,
        min_value: Optional[float] = None,
        mask_path: Optional[str] = None,
        roi: Optional[Tuple[int, int, int, int]] = None,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(mask_path, roi, name)
        self._max_value = max_value
        self._min_value = min_value

    def match(self, image: np.ndarray) -> bool:
        img = self._apply_roi(image)
        level = calculate_brightness(img, self._mask)
        if self._max_value is not None and level > self._max_value:
            logger.debug(
                "明度上限超過", level=float(level), max=self._max_value
            )
            return False
        if self._min_value is not None and level < self._min_value:
            logger.debug(
                "明度下限未満", level=float(level), min=self._min_value
            )
            return False
        return True


class CompositeMatcher:
    """複数条件を評価するマッチャー。"""

    def __init__(
        self,
        expr: MatchExpression,
        lookup: Dict[str, BaseMatcher],
        *,
        name: str | None = None,
    ) -> None:
        self.name = name
        self.expr = expr
        self.lookup = lookup

    def match(self, image: np.ndarray) -> bool:
        """設定された式に基づき判定する。"""

        def _eval(name: str) -> bool:
            matcher = self.lookup.get(name)
            if matcher is None:
                logger.debug("マッチャー未登録", matcher=name)
                return False
            result = matcher.match(image)
            if not result:
                logger.debug("サブマッチャー不一致", matcher=name)
            return result

        result = self.expr.evaluate(_eval)
        if not result:
            logger.debug("複合条件不一致")
        return result


def build_matcher(config: MatcherConfig) -> Optional[BaseMatcher]:
    """設定からマッチャーインスタンスを生成する。"""

    if not config:
        return None

    name = config.name
    mask_path = config.mask_path
    roi_cfg = config.roi
    roi = None
    if roi_cfg:
        roi = (
            roi_cfg.get("x", 0),
            roi_cfg.get("y", 0),
            roi_cfg.get("width", 0),
            roi_cfg.get("height", 0),
        )
    if config.type == "hash" and config.hash_path:
        path = config.hash_path
        try:
            return HashMatcher(path, roi, name=name)
        except Exception:
            return None
    if config.type == "hsv" and config.lower_bound and config.upper_bound:
        return HSVMatcher(
            config.lower_bound,
            config.upper_bound,
            mask_path,
            config.threshold,
            roi,
            name=name,
        )
    if config.type == "rgb" and config.rgb:
        return RGBMatcher(
            config.rgb,
            mask_path,
            config.threshold,
            roi,
            name=name,
        )
    if config.type == "uniform":
        return UniformColorMatcher(
            mask_path,
            config.hue_threshold or 10.0,
            roi,
            name=name,
        )
    if config.type == "brightness" and (
        config.max_value is not None or config.min_value is not None
    ):
        return BrightnessMatcher(
            config.max_value,
            config.min_value,
            mask_path,
            roi,
            name=name,
        )
    if config.type == "template" and config.template_path:
        try:
            return TemplateMatcher(
                config.template_path,
                mask_path,
                config.threshold,
                roi,
                name=name,
            )
        except Exception:
            return None
    return None


def build_composite_matcher(
    name: str, config: CompositeMatcherConfig, lookup: dict[str, BaseMatcher]
) -> Optional[CompositeMatcher]:
    """設定から複合マッチャーを生成する。"""

    if not config or not config.rule:
        return None

    return CompositeMatcher(config.rule, lookup, name=name)


class MatcherRegistry:
    """設定に基づいてマッチャーを管理するクラス。"""

    def __init__(self, settings: ImageMatchingSettings) -> None:
        # 単体マッチャーの登録
        self.matchers: Dict[str, BaseMatcher] = {}
        for name, cfg in settings.matchers.items():
            matcher = build_matcher(cfg)
            if matcher:
                self.matchers[name] = matcher

        # 複合マッチャーの登録
        self.composites: Dict[str, CompositeMatcher] = {}
        for name, comp in settings.composites.items():
            composite = build_composite_matcher(name, comp, self.matchers)
            if composite:
                self.composites[name] = composite

        # グループ定義の登録
        self.groups: Dict[str, list[str]] = settings.matcher_groups

    def match(self, key: str, image: np.ndarray) -> bool:
        """指定されたキーのマッチャーで判定する。"""

        matcher = self.composites.get(key)
        if matcher is None:
            matcher = self.matchers.get(key)
        return matcher.match(image) if matcher else False

    def match_first(self, keys: list[str], image: np.ndarray) -> str | None:
        """複数キーの中から最初に一致したマッチャー名を返す。"""

        for key in keys:
            matcher = self.composites.get(key)
            if matcher is None:
                matcher = self.matchers.get(key)
            if matcher and matcher.match(image):
                return matcher.name or key
        return None

    def match_first_group(self, group: str, image: np.ndarray) -> str | None:
        """グループに登録されたキーから最初に一致した名称を返す。"""

        keys = self.groups.get(group)
        if not keys:
            return None
        return self.match_first(keys, image)


def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    rows, cols = image.shape[:2]
    M = cv2.getRotationMatrix2D((cols/2, rows/2), angle, 1)
    return cv2.warpAffine(image, M, (cols, rows))
