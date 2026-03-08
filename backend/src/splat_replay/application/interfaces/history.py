"""対戦履歴ポート定義。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

__all__ = [
    "BattleHistoryRecord",
    "BattleHistoryRepositoryPort",
]


@dataclass(frozen=True)
class BattleHistoryRecord:
    """1録画分の対戦履歴レコード。"""

    schema_version: int
    source_video_id: str
    created_at: datetime
    updated_at: datetime
    game_mode: str
    started_at: datetime | None = None
    rate: str | None = None
    match: str | None = None
    rule: str | None = None
    stage: str | None = None
    judgement: str | None = None
    kill: int | None = None
    death: int | None = None
    special: int | None = None
    gold_medals: int | None = None
    silver_medals: int | None = None
    allies: tuple[str, str, str, str] | None = None
    enemies: tuple[str, str, str, str] | None = None
    is_partial: bool = False
    missing_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """JSON へ保存できる辞書に変換する。"""
        return {
            "schema_version": self.schema_version,
            "source_video_id": self.source_video_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "game_mode": self.game_mode,
            "started_at": (
                self.started_at.isoformat()
                if self.started_at is not None
                else None
            ),
            "rate": self.rate,
            "match": self.match,
            "rule": self.rule,
            "stage": self.stage,
            "judgement": self.judgement,
            "kill": self.kill,
            "death": self.death,
            "special": self.special,
            "gold_medals": self.gold_medals,
            "silver_medals": self.silver_medals,
            "allies": list(self.allies) if self.allies is not None else None,
            "enemies": list(self.enemies)
            if self.enemies is not None
            else None,
            "is_partial": self.is_partial,
            "missing_fields": list(self.missing_fields),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "BattleHistoryRecord":
        """保存済み辞書からレコードを復元する。"""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        if not isinstance(created_at, str) or not isinstance(updated_at, str):
            raise ValueError("created_at / updated_at が不正です。")
        source_video_id = data.get("source_video_id")
        game_mode = data.get("game_mode")
        if not isinstance(source_video_id, str) or not isinstance(
            game_mode, str
        ):
            raise ValueError("source_video_id / game_mode が不正です。")

        schema_version_raw = data.get("schema_version", 1)
        if isinstance(schema_version_raw, int):
            schema_version = schema_version_raw
        elif isinstance(schema_version_raw, str):
            schema_version = int(schema_version_raw)
        else:
            raise ValueError("schema_version が不正です。")

        started_at_raw = data.get("started_at")
        started_at = (
            datetime.fromisoformat(started_at_raw)
            if isinstance(started_at_raw, str)
            else None
        )

        allies = _parse_weapon_slots(data.get("allies"))
        enemies = _parse_weapon_slots(data.get("enemies"))
        missing_fields = _parse_string_list(data.get("missing_fields"))

        return cls(
            schema_version=schema_version,
            source_video_id=source_video_id,
            created_at=datetime.fromisoformat(created_at),
            updated_at=datetime.fromisoformat(updated_at),
            game_mode=game_mode,
            started_at=started_at,
            rate=_to_optional_str(data.get("rate")),
            match=_to_optional_str(data.get("match")),
            rule=_to_optional_str(data.get("rule")),
            stage=_to_optional_str(data.get("stage")),
            judgement=_to_optional_str(data.get("judgement")),
            kill=_to_optional_int(data.get("kill")),
            death=_to_optional_int(data.get("death")),
            special=_to_optional_int(data.get("special")),
            gold_medals=_to_optional_int(data.get("gold_medals")),
            silver_medals=_to_optional_int(data.get("silver_medals")),
            allies=allies,
            enemies=enemies,
            is_partial=bool(data.get("is_partial", False)),
            missing_fields=missing_fields,
        )


class BattleHistoryRepositoryPort(Protocol):
    """対戦履歴の永続化ポート。"""

    def find_by_source_video_id(
        self, source_video_id: str
    ) -> BattleHistoryRecord | None:
        """動画IDに紐づく履歴を取得する。"""
        ...

    def upsert(self, record: BattleHistoryRecord) -> None:
        """履歴を upsert する。"""
        ...


def _parse_weapon_slots(
    value: object,
) -> tuple[str, str, str, str] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    items = cast(list[str], value)
    return (items[0], items[1], items[2], items[3])


def _parse_string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    if not all(isinstance(item, str) for item in value):
        return ()
    return tuple(cast(list[str], value))


def _to_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _to_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"整数へ変換できません: {value!r}")
