"""Battle-related domain events.

Events related to battle lifecycle and state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from splat_replay.domain.events.base import DomainEvent


@dataclass(frozen=True)
class BattleMatchingStarted(DomainEvent):
    """Battle matching has started."""

    EVENT_TYPE: ClassVar[str] = "domain.battle.matching_started"

    game_mode: str = ""
    rate: str | None = None


@dataclass(frozen=True)
class BattleStarted(DomainEvent):
    """Battle has started (in-game phase)."""

    EVENT_TYPE: ClassVar[str] = "domain.battle.started"

    game_mode: str = ""
    rate: str | None = None
    stage_name: str | None = None


@dataclass(frozen=True)
class BattleInterrupted(DomainEvent):
    """Battle has been interrupted (e.g., communication error)."""

    EVENT_TYPE: ClassVar[str] = "domain.battle.interrupted"

    reason: str = ""


@dataclass(frozen=True)
class BattleFinished(DomainEvent):
    """Battle has finished normally."""

    EVENT_TYPE: ClassVar[str] = "domain.battle.finished"

    duration_seconds: float | None = None


@dataclass(frozen=True)
class BattleResultDetected(DomainEvent):
    """Battle result (win/lose) has been detected."""

    EVENT_TYPE: ClassVar[str] = "domain.battle.result_detected"

    result: str = ""  # "win", "lose", or "unknown"


@dataclass(frozen=True)
class BattleWeaponsDetected(DomainEvent):
    """Battle HUD のブキ判別結果が更新された。"""

    EVENT_TYPE: ClassVar[str] = "domain.battle.weapons_detected"

    allies: list[str] = field(default_factory=list)
    enemies: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    attempt: int = 0
    is_final: bool = False


@dataclass(frozen=True)
class ScheduleChanged(DomainEvent):
    """Game schedule (stage rotation) has changed during matching."""

    EVENT_TYPE: ClassVar[str] = "domain.battle.schedule_changed"


__all__ = [
    "BattleMatchingStarted",
    "BattleStarted",
    "BattleInterrupted",
    "BattleFinished",
    "BattleResultDetected",
    "BattleWeaponsDetected",
    "ScheduleChanged",
]
