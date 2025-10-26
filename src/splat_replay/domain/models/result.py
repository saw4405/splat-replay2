"""Battle and salmon result models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .match import Match
from .rule import Rule
from .stage import Stage


def _as_str(value: object, field: str) -> str:
    if isinstance(value, str):
        return value
    raise TypeError(f"{field} must be str, got {type(value)!r}")


def _as_int(value: object, field: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(
                f"{field} must be an int-compatible string"
            ) from exc
    raise TypeError(f"{field} must be int or str, got {type(value)!r}")


@dataclass
class BattleResult:
    """Result information for a battle."""

    match: Match
    rule: Rule
    stage: Stage
    kill: int
    death: int
    special: int

    def to_dict(self) -> dict[str, str]:
        return {
            "match": self.match.value,
            "rule": self.rule.value,
            "stage": self.stage.value,
            "kill": str(self.kill),
            "death": str(self.death),
            "special": str(self.special),
        }

    def update_from_dict(self, data: Mapping[str, object]) -> None:
        """手動編集されたフィールドで部分的に更新する。"""
        if "match" in data:
            try:
                self.match = Match(_as_str(data["match"], "match"))
            except Exception:
                pass
        if "rule" in data:
            try:
                self.rule = Rule(_as_str(data["rule"], "rule"))
            except Exception:
                pass
        if "stage" in data:
            try:
                self.stage = Stage(_as_str(data["stage"], "stage"))
            except Exception:
                pass
        if "kill" in data:
            try:
                self.kill = _as_int(data["kill"], "kill")
            except Exception:
                pass
        if "death" in data:
            try:
                self.death = _as_int(data["death"], "death")
            except Exception:
                pass
        if "special" in data:
            try:
                self.special = _as_int(data["special"], "special")
            except Exception:
                pass

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "BattleResult":
        match_str = _as_str(data["match"], "match")
        rule_str = _as_str(data["rule"], "rule")
        stage_str = _as_str(data["stage"], "stage")
        kill = _as_int(data["kill"], "kill")
        death = _as_int(data["death"], "death")
        special = _as_int(data["special"], "special")
        return cls(
            match=Match(match_str),
            rule=Rule(rule_str),
            stage=Stage(stage_str),
            kill=kill,
            death=death,
            special=special,
        )


@dataclass
class SalmonResult:
    """Result information for a salmon run."""

    hazard: int
    stage: Stage
    golden_egg: int
    power_egg: int
    rescue: int
    rescued: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "hazard": self.hazard,
            "stage": self.stage.name,
            "golden_egg": self.golden_egg,
            "power_egg": self.power_egg,
            "rescue": self.rescue,
            "rescued": self.rescued,
        }

    def update_from_dict(self, data: Mapping[str, object]) -> None:
        """手動編集されたフィールドで部分的に更新する。"""
        if "hazard" in data:
            try:
                self.hazard = _as_int(data["hazard"], "hazard")
            except Exception:
                pass
        if "stage" in data:
            try:
                self.stage = Stage[_as_str(data["stage"], "stage")]
            except Exception:
                pass
        if "golden_egg" in data:
            try:
                self.golden_egg = _as_int(data["golden_egg"], "golden_egg")
            except Exception:
                pass
        if "power_egg" in data:
            try:
                self.power_egg = _as_int(data["power_egg"], "power_egg")
            except Exception:
                pass
        if "rescue" in data:
            try:
                self.rescue = _as_int(data["rescue"], "rescue")
            except Exception:
                pass
        if "rescued" in data:
            try:
                self.rescued = _as_int(data["rescued"], "rescued")
            except Exception:
                pass

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SalmonResult":
        hazard = _as_int(data["hazard"], "hazard")
        stage_name = _as_str(data["stage"], "stage")
        golden = _as_int(data["golden_egg"], "golden_egg")
        power = _as_int(data["power_egg"], "power_egg")
        rescue_value = _as_int(data["rescue"], "rescue")
        rescued_value = _as_int(data["rescued"], "rescued")
        return cls(
            hazard=hazard,
            stage=Stage[stage_name],
            golden_egg=golden,
            power_egg=power,
            rescue=rescue_value,
            rescued=rescued_value,
        )


Result = BattleResult | SalmonResult
