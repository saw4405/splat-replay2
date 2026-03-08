"""メタデータ管理関連のDTO定義。"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Mapping, TypeAlias, cast

__all__ = [
    "SubtitleDTO",
    "RecordingMetadataPatchDTO",
]

WeaponSlots: TypeAlias = tuple[str, str, str, str]
MetadataUpdateInputValue: TypeAlias = str | int | WeaponSlots
MetadataUpdateInput: TypeAlias = dict[str, MetadataUpdateInputValue]


def _as_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _as_weapon_slots(
    value: object,
) -> WeaponSlots | None:
    if (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, str) for item in value)
    ):
        return cast(
            tuple[str, str, str, str],
            (value[0], value[1], value[2], value[3]),
        )
    return None


@dataclass(frozen=True)
class SubtitleDTO:
    """字幕データを表すDTO。

    Attributes:
        content: 字幕内容（SRT形式のテキスト）
    """

    content: str


@dataclass(frozen=True)
class RecordingMetadataPatchDTO:
    """録画メタデータ更新パッチDTO。"""

    match: str | None = None
    rule: str | None = None
    stage: str | None = None
    rate: str | None = None
    judgement: str | None = None
    kill: int | None = None
    death: int | None = None
    special: int | None = None
    gold_medals: int | None = None
    silver_medals: int | None = None
    allies: WeaponSlots | None = None
    enemies: WeaponSlots | None = None

    @classmethod
    def from_update_dict(
        cls, data: Mapping[str, object]
    ) -> RecordingMetadataPatchDTO:
        """外部入力の辞書から更新 DTO を組み立てる。"""
        return cls(
            match=_as_optional_str(data.get("match")),
            rule=_as_optional_str(data.get("rule")),
            stage=_as_optional_str(data.get("stage")),
            rate=_as_optional_str(data.get("rate")),
            judgement=_as_optional_str(data.get("judgement")),
            kill=_as_optional_int(data.get("kill")),
            death=_as_optional_int(data.get("death")),
            special=_as_optional_int(data.get("special")),
            gold_medals=_as_optional_int(data.get("gold_medals")),
            silver_medals=_as_optional_int(data.get("silver_medals")),
            allies=_as_weapon_slots(data.get("allies")),
            enemies=_as_weapon_slots(data.get("enemies")),
        )

    def to_metadata_update_dict(self) -> MetadataUpdateInput:
        """metadata parser 向けの内部更新辞書を返す。"""
        return {
            field.name: value
            for field in fields(self)
            if (value := getattr(self, field.name)) is not None
        }
