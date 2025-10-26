from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Optional, Protocol

import numpy as np

from splat_replay.domain.services import ImageMatcherPort
from splat_replay.shared.config import (
    CompositeMatcherConfig,
    ImageMatchingSettings,
    MatcherConfig,
)
from splat_replay.shared.paths import PROJECT_ROOT

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

    def _get_matcher(self, key: str) -> MatcherLike | None:
        composite = self.composites.get(key)
        if composite is not None:
            return composite
        return self.matchers.get(key)

    def _build_matcher(self, config: MatcherConfig) -> Optional[BaseMatcher]:
        if not config:
            return None

        name = config.name

        # mask_path を絶対パスに変換
        mask_path = None
        if config.mask_path:
            mask_path = Path(config.mask_path)
            if not mask_path.is_absolute():
                mask_path = PROJECT_ROOT / mask_path

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
                # 相対パスの場合はPROJECT_ROOTからの絶対パスに変換
                hash_path = Path(config.hash_path)
                if not hash_path.is_absolute():
                    hash_path = PROJECT_ROOT / hash_path
                return HashMatcher(hash_path, roi, name=name)
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
                # 相対パスの場合はPROJECT_ROOTからの絶対パスに変換
                template_path = Path(config.template_path)
                if not template_path.is_absolute():
                    template_path = PROJECT_ROOT / template_path
                return TemplateMatcher(
                    template_path,
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
                # 相対パスの場合はPROJECT_ROOTからの絶対パスに変換
                template_path = Path(config.template_path)
                if not template_path.is_absolute():
                    template_path = PROJECT_ROOT / template_path
                return EdgeMatcher(
                    template_path,
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
        matcher = self._get_matcher(key)
        result = await matcher.match(image) if matcher else False
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
        keys = self.groups.get(group)
        if not keys:
            return None
        result = await self.match_first(keys, image)
        return result
