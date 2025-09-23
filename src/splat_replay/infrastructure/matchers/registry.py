from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Optional, Protocol, Tuple

import numpy as np

from splat_replay.domain.services import ImageMatcherPort
from splat_replay.shared.config import (
    CompositeMatcherConfig,
    ImageMatchingSettings,
    MatcherConfig,
)

from .base import BaseMatcher
from .brightness import BrightnessMatcher
from .composite import CompositeMatcher
from .edge import EdgeMatcher
from .hash import HashMatcher
from .hsv import HSVMatcher
from .hsv_ratio import HSVRatioMatcher
from .rgb import RGBMatcher
from .template import TemplateMatcher
from .uniform import UniformColorMatcher


class MatcherLike(Protocol):
    name: str | None

    async def match(self, image: np.ndarray) -> bool: ...


class MatcherRegistry(ImageMatcherPort):
    """設定に基づいてマッチャーを管理するクラス。"""

    def __init__(self, settings: ImageMatchingSettings) -> None:
        self.matchers: Dict[str, BaseMatcher] = {}
        for name, cfg in settings.matchers.items():
            matcher = self._build_matcher(cfg)
            if matcher:
                self.matchers[name] = matcher

        self.composites: Dict[str, CompositeMatcher] = {}
        for name, comp in settings.composites.items():
            composite = self._build_composite_matcher(
                name, comp, self.matchers
            )
            if composite:
                self.composites[name] = composite

        self.groups: Dict[str, list[str]] = settings.matcher_groups

        # 軽量キャッシュ: (キー/グループ, フィンガープリント) -> 結果
        self._match_cache: Dict[Tuple[str, int], bool] = {}
        self._matched_name_cache: Dict[Tuple[str, int], Optional[str]] = {}

    def _get_matcher(self, key: str) -> MatcherLike | None:
        composite = self.composites.get(key)
        if composite is not None:
            return composite
        return self.matchers.get(key)

    def _fingerprint(self, image: np.ndarray) -> int:
        """高速な簡易フィンガープリント。

        画素を粗くサンプリングし、単純合計で 32bit に収める。
        同一フレームの反復照合を高速化するための近似キーとして利用。
        """
        # BGR の B チャネルのみサンプリングして軽量化
        sample = image[::64, ::64, 0]
        return int(sample.sum()) & 0xFFFFFFFF

    def _build_matcher(self, config: MatcherConfig) -> Optional[BaseMatcher]:
        if not config:
            return None

        name = config.name
        mask_path = Path(config.mask_path) if config.mask_path else None
        roi_cfg = config.roi
        roi = None
        if roi_cfg:
            roi = (
                roi_cfg.get("x", 0),
                roi_cfg.get("y", 0),
                roi_cfg.get("width", 0),
                roi_cfg.get("height", 0),
            )
        if config.type == "hash":
            if config.hash_path:
                return HashMatcher(Path(config.hash_path), roi, name=name)
            else:
                raise ValueError("ハッシュマッチャーには hash_path が必要です")
        if config.type == "hsv":
            if config.lower_bound and config.upper_bound:
                return HSVMatcher(
                    config.lower_bound,
                    config.upper_bound,
                    mask_path,
                    config.threshold,
                    roi,
                    name=name,
                )
            else:
                raise ValueError(
                    "HSVマッチャーには lower_bound と upper_bound が必要です"
                )
        if config.type == "hsv_ratio":
            if config.lower_bound and config.upper_bound:
                return HSVRatioMatcher(
                    config.lower_bound,
                    config.upper_bound,
                    config.threshold,
                    roi,
                    name=name,
                )
            else:
                raise ValueError(
                    "HSV比率マッチャーには lower_bound と upper_bound が必要です"
                )
        if config.type == "rgb":
            if config.rgb:
                return RGBMatcher(
                    config.rgb,
                    mask_path,
                    config.threshold,
                    roi,
                    name=name,
                )
            else:
                raise ValueError("RGBマッチャーには rgb が必要です")
        if config.type == "uniform":
            return UniformColorMatcher(
                mask_path,
                config.hue_threshold or 10.0,
                roi,
                name=name,
            )
        if config.type == "brightness":
            if config.max_value is not None or config.min_value is not None:
                return BrightnessMatcher(
                    config.max_value,
                    config.min_value,
                    mask_path,
                    roi,
                    name=name,
                )
            else:
                raise ValueError(
                    "明度マッチャーには max_value または min_value が必要です"
                )
        if config.type == "template":
            if config.template_path:
                return TemplateMatcher(
                    Path(config.template_path),
                    mask_path,
                    config.threshold,
                    roi,
                    name=name,
                )
            else:
                raise ValueError(
                    "テンプレートマッチャーには template_path が必要です"
                )
        if config.type == "edge":
            if config.template_path:
                return EdgeMatcher(
                    Path(config.template_path),
                    config.threshold,
                    roi,
                    name=name,
                )
            else:
                raise ValueError(
                    "テンプレートマッチャーには template_path が必要です"
                )
        raise ValueError(f"不明なマッチャータイプ: {config.type}")

    def _build_composite_matcher(
        self,
        name: str,
        config: CompositeMatcherConfig,
        lookup: dict[str, BaseMatcher],
    ) -> Optional[CompositeMatcher]:
        if not config or not config.rule:
            return None
        return CompositeMatcher(config.rule, lookup, name=name)

    async def match(self, key: str, image: np.ndarray) -> bool:
        fp = self._fingerprint(image)
        cached = self._match_cache.get((key, fp))
        if cached is not None:
            return cached

        matcher = self._get_matcher(key)
        result = await matcher.match(image) if matcher else False
        self._match_cache[(key, fp)] = result
        return result

    async def match_first(
        self, keys: list[str], image: np.ndarray
    ) -> str | None:
        # For small groups, evaluate in parallel to reduce wall time.
        if len(keys) <= 4:
            tasks: list[asyncio.Task[bool]] = []
            matchers: list[MatcherLike | None] = []
            for key in keys:
                matcher = self._get_matcher(key)
                matchers.append(matcher)
                if matcher is not None:
                    tasks.append(asyncio.create_task(matcher.match(image)))
                else:
                    tasks.append(
                        asyncio.create_task(asyncio.sleep(0, result=False))
                    )

            results = await asyncio.gather(*tasks)
            for key, matcher, ok in zip(keys, matchers, results):
                if matcher is not None and ok:
                    return matcher.name or key
            return None

        # Fallback: sequential evaluation to avoid spawning many tasks.
        for key in keys:
            matcher = self._get_matcher(key)
            if matcher and await matcher.match(image):
                return matcher.name or key
        return None

    async def matched_name(self, group: str, image: np.ndarray) -> str | None:
        fp = self._fingerprint(image)
        cached = self._matched_name_cache.get((group, fp))
        if cached is not None:
            return cached

        keys = self.groups.get(group)
        if not keys:
            self._matched_name_cache[(group, fp)] = None
            return None
        result = await self.match_first(keys, image)
        self._matched_name_cache[(group, fp)] = result
        return result
