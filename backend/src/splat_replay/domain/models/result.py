"""Battle and salmon result models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, TypeVar

from splat_replay.domain.exceptions import ValidationError

from .match import Match
from .rule import Rule
from .stage import Stage

MEDAL_COUNT_MIN = 0
MEDAL_COUNT_MAX = 3
MEDAL_COUNT_TOTAL_MAX = 3


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


TEnum = TypeVar("TEnum", bound=Enum)


def _as_optional_enum_member(
    value: object, enum_type: type[TEnum], field: str
) -> TEnum | None:
    if value is None or value == "":
        return None
    name = _as_str(value, field)
    try:
        return enum_type[name]
    except KeyError as exc:
        raise ValidationError(
            f"{field} has invalid enum name: {name}",
            error_code="FIELD_INVALID_ENUM_NAME",
            cause=exc,
        ) from exc


def validate_medal_counts(gold_medals: int, silver_medals: int) -> None:
    if not (MEDAL_COUNT_MIN <= gold_medals <= MEDAL_COUNT_MAX):
        raise ValidationError(
            f"gold_medals は {MEDAL_COUNT_MIN} 以上 {MEDAL_COUNT_MAX} 以下で指定してください",
            error_code="GOLD_MEDALS_OUT_OF_RANGE",
        )
    if not (MEDAL_COUNT_MIN <= silver_medals <= MEDAL_COUNT_MAX):
        raise ValidationError(
            f"silver_medals は {MEDAL_COUNT_MIN} 以上 {MEDAL_COUNT_MAX} 以下で指定してください",
            error_code="SILVER_MEDALS_OUT_OF_RANGE",
        )
    if gold_medals + silver_medals > MEDAL_COUNT_TOTAL_MAX:
        raise ValidationError(
            f"gold_medals と silver_medals の合計は {MEDAL_COUNT_TOTAL_MAX} 以下で指定してください",
            error_code="MEDAL_COUNT_TOTAL_OUT_OF_RANGE",
        )


@dataclass(frozen=True)
class BattleResult:
    """Result information for a battle.

    Immutable Value Object representing battle result data.
    Use dataclasses.replace() for updates.
    """

    match: Match | None
    rule: Rule | None
    stage: Stage | None
    kill: int
    death: int
    special: int
    gold_medals: int = 0
    silver_medals: int = 0

    def __post_init__(self) -> None:
        validate_medal_counts(self.gold_medals, self.silver_medals)

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "match": self.match.name if self.match is not None else None,
            "rule": self.rule.name if self.rule is not None else None,
            "stage": self.stage.name if self.stage is not None else None,
            "kill": self.kill,
            "death": self.death,
            "special": self.special,
            "gold_medals": self.gold_medals,
            "silver_medals": self.silver_medals,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "BattleResult":
        kill = _as_int(data["kill"], "kill")
        death = _as_int(data["death"], "death")
        special = _as_int(data["special"], "special")
        gold_medals = _as_int(data.get("gold_medals", 0), "gold_medals")
        silver_medals = _as_int(data.get("silver_medals", 0), "silver_medals")
        return cls(
            match=_as_optional_enum_member(data.get("match"), Match, "match"),
            rule=_as_optional_enum_member(data.get("rule"), Rule, "rule"),
            stage=_as_optional_enum_member(data.get("stage"), Stage, "stage"),
            kill=kill,
            death=death,
            special=special,
            gold_medals=gold_medals,
            silver_medals=silver_medals,
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
