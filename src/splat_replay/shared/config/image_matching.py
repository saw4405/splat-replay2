"""Image matching configuration models."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import (
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Tuple,
    cast,
)

from pydantic import BaseModel, Field, validator


class MatchExpression(BaseModel):
    """Boolean matcher expression tree."""

    matcher: Optional[str] = None
    not_: Optional["MatchExpression"] = Field(default=None, alias="not")
    and_: Optional[List["MatchExpression"]] = Field(default=None, alias="and")
    or_: Optional[List["MatchExpression"]] = Field(default=None, alias="or")

    class Config:
        allow_population_by_field_name = True

    @validator("not_", pre=True)
    def _convert_not(cls, value: object) -> object:
        if isinstance(value, dict):
            return MatchExpression.parse_obj(value)
        return value

    @validator("and_", "or_", pre=True)
    def _convert_list(cls, value: object) -> object:
        if isinstance(value, list):
            return [
                MatchExpression.parse_obj(item)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        return value

    async def evaluate(self, fn: Callable[[str], Awaitable[bool]]) -> bool:
        """Evaluate the expression using the provided matcher callback."""
        if self.matcher is not None:
            return await fn(self.matcher)

        if self.not_ is not None:
            return not await self.not_.evaluate(fn)

        if self.and_ is not None:
            results = await asyncio.gather(
                *(expr.evaluate(fn) for expr in self.and_)
            )
            return all(results)

        if self.or_ is not None:
            results = await asyncio.gather(
                *(expr.evaluate(fn) for expr in self.or_)
            )
            return any(results)

        return False


MatchExpression.update_forward_refs()


class MatcherConfig(BaseModel):
    """Configuration for a single matcher."""

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
    """Composite matcher made of multiple simple matchers."""

    rule: MatchExpression


class ImageMatchingSettings(BaseModel):
    """Repository of matcher definitions."""

    matchers: Dict[str, MatcherConfig] = {}
    composites: Dict[str, CompositeMatcherConfig] = {}
    matcher_groups: Dict[str, List[str]] = {}

    @classmethod
    def load_from_yaml(cls, path: Path) -> "ImageMatchingSettings":
        """Load configuration from YAML."""
        import yaml

        with path.open("rb") as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            raise ValueError("image matching config must be a mapping")

        raw = cast(Dict[str, object], data)

        matchers: Dict[str, MatcherConfig] = {}
        simple_raw = raw.get("simple_matchers", {})
        if not isinstance(simple_raw, dict):
            raise ValueError("simple_matchers must be a mapping")

        for name, cfg in simple_raw.items():
            if not isinstance(name, str):
                raise ValueError("simple_matchers keys must be strings")
            if not isinstance(cfg, dict):
                raise ValueError("simple_matchers values must be mappings")
            matchers[name] = MatcherConfig.parse_obj(cfg)

        composites: Dict[str, CompositeMatcherConfig] = {}
        composite_raw = raw.get("composite_detection", {})
        if not isinstance(composite_raw, dict):
            raise ValueError("composite_detection must be a mapping")
        for name, cfg in composite_raw.items():
            if not isinstance(name, str):
                raise ValueError("composite_detection keys must be strings")
            composites[name] = CompositeMatcherConfig(
                rule=MatchExpression.parse_obj(cfg)
            )

        groups: Dict[str, List[str]] = {}
        groups_raw = raw.get("matcher_groups", {})
        if not isinstance(groups_raw, dict):
            raise ValueError("matcher_groups must be a mapping")
        for name, keys in groups_raw.items():
            if not isinstance(name, str):
                raise ValueError("matcher_groups keys must be strings")
            if not isinstance(keys, Iterable):
                raise ValueError("matcher_groups values must be iterable")
            groups[name] = [str(key) for key in keys]

        return cls(
            matchers=matchers,
            composites=composites,
            matcher_groups=groups,
        )

    class Config:
        pass
