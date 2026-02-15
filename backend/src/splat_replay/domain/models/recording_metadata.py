"""Recording metadata aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Mapping

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

    # ----------------------------------------------------------------
    # フィールド定義（クラス定数）
    # ----------------------------------------------------------------

    # メタデータの共通フィールド
    ALL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "game_mode",
            "started_at",
            "rate",
            "judgement",
            "allies",
            "enemies",
        }
    )

    # バトルモード固有のフィールド
    BATTLE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "match",
            "rule",
            "stage",
            "kill",
            "death",
            "special",
        }
    )

    # サーモンラン固有のフィールド
    SALMON_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "stage",
            "hazard",
            "golden_egg",
            "power_egg",
            "rescue",
            "rescued",
        }
    )

    # 手動編集可能なフィールド（ALL_FIELDS + BATTLE_FIELDS + SALMON_FIELDS）
    EDITABLE_FIELDS: ClassVar[frozenset[str]] = (
        ALL_FIELDS | BATTLE_FIELDS | SALMON_FIELDS
    )

    # ----------------------------------------------------------------
    # データフィールド
    # ----------------------------------------------------------------

    game_mode: GameMode = GameMode.BATTLE
    started_at: datetime | None = None
    rate: RateBase | None = None
    judgement: Judgement | None = None
    allies: tuple[str, str, str, str] | None = None
    enemies: tuple[str, str, str, str] | None = None
    result: Result | None = None

    def to_dict(self) -> dict[str, str | int | list[str] | None]:
        """Serialize into a JSON-friendly dictionary."""
        payload: dict[str, str | int | list[str] | None] = {
            "game_mode": self.game_mode.name,
            "started_at": self.started_at.isoformat()
            if self.started_at
            else None,
            "rate": str(self.rate) if self.rate else None,
            "judgement": self.judgement.name if self.judgement else None,
            "allies": list(self.allies) if self.allies else None,
            "enemies": list(self.enemies) if self.enemies else None,
        }
        if self.result:
            payload.update(self.result.to_dict())
        return payload

    @classmethod
    def get_field_category(cls, field_name: str) -> str | None:
        """フィールドのカテゴリを取得する。

        Args:
            field_name: フィールド名

        Returns:
            カテゴリ名（"common" | "battle" | "salmon" | None）
        """
        if field_name in cls.ALL_FIELDS:
            return "common"
        if field_name in cls.BATTLE_FIELDS:
            return "battle"
        if field_name in cls.SALMON_FIELDS:
            return "salmon"
        return None

    @classmethod
    def is_editable(cls, field_name: str) -> bool:
        """フィールドが手動編集可能かどうかを判定する。

        Args:
            field_name: フィールド名

        Returns:
            編集可能な場合 True
        """
        return field_name in cls.EDITABLE_FIELDS

    # from_dict メソッドは application.services.metadata_parser.MetadataParser に移動しました。
    # パース処理は Application 層の責務です。
