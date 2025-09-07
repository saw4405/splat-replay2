from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

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

    def to_dict(self) -> Dict[str, str]:
        return {
            "match": self.match.value,
            "rule": self.rule.value,
            "stage": self.stage.value,
            "kill": str(self.kill),
            "death": str(self.death),
            "special": str(self.special),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "BattleResult":
        return cls(
            match=Match(data["match"]),
            rule=Rule(data["rule"]),
            stage=Stage(data["stage"]),
            kill=int(data["kill"]),
            death=int(data["death"]),
            special=int(data["special"]),
        )


@dataclass
class SalmonResult:
    """サーモンラン結果で取得したメタデータ。"""

    hazard: int
    stage: Stage
    golden_egg: int
    power_egg: int
    rescue: int
    rescued: int

    def to_dict(self) -> dict:
        return {
            "hazard": self.hazard,
            "stage": self.stage.name,
            "golden_egg": self.golden_egg,
            "power_egg": self.power_egg,
            "rescue": self.rescue,
            "rescued": self.rescued,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SalmonResult":
        from .stage import Stage

        return cls(
            hazard=data["hazard"],
            stage=Stage[data["stage"]],
            golden_egg=data["golden_egg"],
            power_egg=data["power_egg"],
            rescue=data["rescue"],
            rescued=data["rescued"],
        )


Result = BattleResult | SalmonResult
