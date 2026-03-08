"""Recording metadata aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .game_mode import GameMode
from .judgement import Judgement
from .rate import RateBase
from .result import Result

__all__ = ["RecordingMetadata"]


@dataclass(frozen=True)
class RecordingMetadata:
    """State captured during an automated recording session.

    Immutable Value Object representing metadata for a single recording.
    Use dataclasses.replace() for updates, or RecordingMetadata() for reset.
    """

    game_mode: GameMode = GameMode.BATTLE
    started_at: datetime | None = None
    rate: RateBase | None = None
    judgement: Judgement | None = None
    allies: tuple[str, str, str, str] | None = None
    enemies: tuple[str, str, str, str] | None = None
    result: Result | None = None
