from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Literal, Optional, Tuple

import asyncio
from pydantic import BaseModel, Field, validator


class MatchExpression(BaseModel):
    """マッチング条件を組み合わせるための表現。"""

    matcher: Optional[str] = None
    not_: Optional["MatchExpression"] = Field(default=None, alias="not")
    and_: Optional[List["MatchExpression"]] = Field(default=None, alias="and")
    or_: Optional[List["MatchExpression"]] = Field(default=None, alias="or")

    class Config:
        allow_population_by_field_name = True

    @validator("not_", pre=True)
    def _convert_not(cls, v: object) -> object:
        """辞書で渡された場合に再帰的に変換する。"""
        if isinstance(v, dict):
            return MatchExpression.parse_obj(v)
        return v

    @validator("and_", "or_", pre=True)
    def _convert_list(cls, v: object) -> object:
        """リスト要素を `MatchExpression` に変換する。"""
        if isinstance(v, list):
            return [
                MatchExpression.parse_obj(i) if isinstance(i, dict) else i
                for i in v
            ]
        return v

    async def evaluate(self, fn: Callable[[str], Awaitable[bool]]) -> bool:
        """与えられた評価関数を用いて式を判定する。

        - matcher: 直接評価
        - not: 否定を評価（再帰）
        - and: 並列に評価して全て True か
        - or: 並列に評価していずれか True か
        """
        if self.matcher is not None:
            return await fn(self.matcher)

        if self.not_ is not None:
            return not await self.not_.evaluate(fn)

        if self.and_ is not None:
            # Evaluate all branches concurrently to minimize wall time.
            results = await asyncio.gather(
                *(expr.evaluate(fn) for expr in self.and_)
            )
            return all(results)

        if self.or_ is not None:
            # Evaluate in parallel and check if any passes.
            results = await asyncio.gather(
                *(expr.evaluate(fn) for expr in self.or_)
            )
            return any(results)

        return False


MatchExpression.update_forward_refs()


class MatcherConfig(BaseModel):
    """画像マッチング1件分の設定。"""

    name: Optional[str] = None
    type: Literal[
        "template",
        "hsv",
        "hsv_ratio",
        "rgb",
        "hash",
        "uniform",
        "brightness",
        "edge",
    ]
    threshold: float = 0.8
    template_path: Optional[str] = None
    hash_path: Optional[str] = None
    lower_bound: Optional[Tuple[int, int, int]] = None
    upper_bound: Optional[Tuple[int, int, int]] = None
    rgb: Optional[Tuple[int, int, int]] = None
    hue_threshold: Optional[float] = None
    mask_path: Optional[str] = None
    max_value: Optional[float] = None
    min_value: Optional[float] = None
    roi: Optional[Dict[str, int]] = None


class CompositeMatcherConfig(BaseModel):
    """複合条件を表す設定。"""

    rule: MatchExpression


class ImageMatchingSettings(BaseModel):
    """画像解析用のマッチャー設定。"""

    matchers: Dict[str, MatcherConfig] = {}
    composites: Dict[str, CompositeMatcherConfig] = {}
    matcher_groups: Dict[str, List[str]] = {}

    @classmethod
    def load_from_yaml(cls, path: Path) -> "ImageMatchingSettings":
        """YAML ファイルから設定を読み込む。"""
        import yaml

        with path.open("rb") as f:
            raw = yaml.safe_load(f) or {}
        matchers: Dict[str, MatcherConfig] = {}
        for name, cfg in raw.get("simple_matchers", {}).items():
            matchers[name] = MatcherConfig(**cfg)
        composites: Dict[str, CompositeMatcherConfig] = {}
        for name, cfg in raw.get("composite_detection", {}).items():
            expr = MatchExpression.parse_obj(cfg)
            composites[name] = CompositeMatcherConfig(rule=expr)
        groups: Dict[str, List[str]] = {}
        for name, keys in raw.get("matcher_groups", {}).items():
            groups[name] = list(keys)
        return cls(
            matchers=matchers,
            composites=composites,
            matcher_groups=groups,
        )

    class Config:
        pass
