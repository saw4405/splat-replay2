from __future__ import annotations

from dataclasses import dataclass

from .match import Match
from .rule import Rule
from .stage import Stage


@dataclass
class BattleResult:
    """結果画面で取得したメタデータ。"""

    match: Match
    rule: Rule
    stage: Stage
    kill: int
    death: int
    special: int


@dataclass
class SalmonResult:
    """サーモンラン結果で取得したメタデータ。"""

    hazard: int
    stage: Stage
    golden_egg: int
    power_egg: int
    rescue: int
    rescued: int


Result = BattleResult | SalmonResult
