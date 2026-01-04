"""Battle and salmon result models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from splat_replay.domain.exceptions import ValidationError

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
            raise ValidationError(
                f"{field} must be an int-compatible string",
                error_code="FIELD_NOT_INT_COMPATIBLE",
                cause=exc,
            ) from exc
    raise TypeError(f"{field} must be int or str, got {type(value)!r}")


@dataclass(frozen=True)
class BattleResult:
    """Result information for a battle.

    Immutable Value Object representing battle result data.
    Use dataclasses.replace() for updates.
    """

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


@dataclass(frozen=True)
class SalmonResult:
    """Result information for a salmon run.

    Immutable Value Object representing salmon run result data.
    Use dataclasses.replace() for updates.
    """

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
