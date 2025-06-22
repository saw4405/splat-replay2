"""画像マッチング条件を論理式として扱うモデル。"""

from __future__ import annotations

from typing import Callable, List, Optional

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
            return [MatchExpression.parse_obj(i) if isinstance(i, dict) else i for i in v]
        return v

    def evaluate(self, fn: Callable[[str], bool]) -> bool:
        """与えられた評価関数を用いて式を判定する。"""
        if self.matcher is not None:
            return fn(self.matcher)
        if self.not_ is not None:
            return not self.not_.evaluate(fn)
        if self.and_ is not None:
            return all(expr.evaluate(fn) for expr in self.and_)
        if self.or_ is not None:
            return any(expr.evaluate(fn) for expr in self.or_)
        return False


MatchExpression.update_forward_refs()
