"""Recording metadata aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .game_mode import GameMode
from .judgement import Judgement
from .rate import RateBase
from .result import Result

__all__ = [
    "RecordingMetadata",
    "has_required_fields",
    "BATTLE_RESULT_REQUIRED_FIELDS",
    "SALMON_RESULT_REQUIRED_FIELDS",
]


def has_required_fields(
    data: Mapping[str, object], required_fields: tuple[str, ...]
) -> bool:
    """Check if all required fields are present and non-empty in data.

    Args:
        data: Mapping to check
        required_fields: Tuple of required field names

    Returns:
        True if all required fields are present and non-empty
    """
    for field in required_fields:
        if field not in data:
            return False
        value = data.get(field)
        if value is None:
            return False
        if isinstance(value, str) and not value:
            return False
    return True


BATTLE_RESULT_REQUIRED_FIELDS: tuple[str, ...] = (
    "match",
    "rule",
    "stage",
    "kill",
    "death",
    "special",
)

SALMON_RESULT_REQUIRED_FIELDS: tuple[str, ...] = (
    "hazard",
    "stage",
    "golden_egg",
    "power_egg",
    "rescue",
    "rescued",
)


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
    result: Result | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        """Serialize into a JSON-friendly dictionary."""
        payload: dict[str, str | int | None] = {
            "game_mode": self.game_mode.value,
            "started_at": self.started_at.isoformat()
            if self.started_at
            else None,
            "rate": str(self.rate) if self.rate else None,
            "judgement": self.judgement.value if self.judgement else None,
        }
        if self.result:
            payload.update(self.result.to_dict())
        return payload

    # from_dict メソッドは application.services.metadata_parser.MetadataParser に移動しました。
    # パース処理は Application 層の責務です。
