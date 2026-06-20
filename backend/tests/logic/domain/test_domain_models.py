"""Domain Models Unit Tests.

責務：
- Domain 層の値オブジェクト（Enum）の独自メソッドを検証する
- シリアライズ用の value 文字列を確認する
- 標準ライブラリが保証する動作（==, is, list(), in）は再テストしない

分類: logic
"""

from __future__ import annotations

from enum import Enum
from typing import Type

import pytest

from splat_replay.domain.models import GameMode, Judgement, Match, Rule, Stage


@pytest.mark.parametrize(
    "enum_cls",
    [Match, Rule, Stage, Judgement, GameMode],
    ids=lambda c: c.__name__,
)
def test_enum_values_are_unique(enum_cls: Type[Enum]) -> None:
    """各 Enum の value が重複していないことを確認。"""
    values = [member.value for member in enum_cls]
    assert len(values) == len(set(values))


class TestMatch:
    """Match モデルの独自メソッドのテスト。"""

    def test_is_anarchy(self) -> None:
        """is_anarchy() が正しくバンカラ系を判定する。"""
        assert Match.ANARCHY.is_anarchy()
        assert Match.ANARCHY_OPEN.is_anarchy()
        assert Match.ANARCHY_SERIES.is_anarchy()
        assert not Match.REGULAR.is_anarchy()
        assert not Match.X.is_anarchy()
        assert not Match.SPLATFEST.is_anarchy()

    def test_is_fest(self) -> None:
        """is_fest() が正しくフェス系を判定する。"""
        assert Match.SPLATFEST.is_fest()
        assert Match.SPLATFEST_OPEN.is_fest()
        assert Match.SPLATFEST_PRO.is_fest()
        assert not Match.REGULAR.is_fest()
        assert not Match.ANARCHY.is_fest()
        assert not Match.X.is_fest()

    def test_equal_same_variant(self) -> None:
        """同じバリアントの等値性テスト。"""
        assert Match.REGULAR.equal(Match.REGULAR)
        assert Match.ANARCHY.equal(Match.ANARCHY)

    def test_equal_different_variant_strict(self) -> None:
        """異なるバリアントの等値性テスト（厳密モード）。"""
        assert not Match.ANARCHY_OPEN.equal(Match.ANARCHY_SERIES)
        assert not Match.SPLATFEST_OPEN.equal(Match.SPLATFEST_PRO)
        assert not Match.REGULAR.equal(Match.ANARCHY)

    def test_equal_ignore_open_challenge_anarchy(self) -> None:
        """equal() の ignore_open_challenge オプション（バンカラ）。"""
        assert Match.ANARCHY_OPEN.equal(
            Match.ANARCHY_SERIES, ignore_open_challenge=True
        )
        assert Match.ANARCHY.equal(
            Match.ANARCHY_OPEN, ignore_open_challenge=True
        )
        assert Match.ANARCHY.equal(
            Match.ANARCHY_SERIES, ignore_open_challenge=True
        )

    def test_equal_ignore_open_challenge_fest(self) -> None:
        """equal() の ignore_open_challenge オプション（フェス）。"""
        assert Match.SPLATFEST_OPEN.equal(
            Match.SPLATFEST_PRO, ignore_open_challenge=True
        )
        assert Match.SPLATFEST.equal(
            Match.SPLATFEST_OPEN, ignore_open_challenge=True
        )
        assert Match.SPLATFEST.equal(
            Match.SPLATFEST_PRO, ignore_open_challenge=True
        )

    def test_equal_cross_category_with_ignore(self) -> None:
        """異なるカテゴリでは ignore_open_challenge でも一致しない。"""
        assert not Match.ANARCHY.equal(
            Match.SPLATFEST, ignore_open_challenge=True
        )
        assert not Match.REGULAR.equal(
            Match.ANARCHY, ignore_open_challenge=True
        )
