"""録画メタデータのフィールド定義。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Mapping

from splat_replay.domain.models import GameMode, Judgement, Match, Rule, Stage

MetadataFieldCategory = Literal["common", "battle", "salmon"]
MetadataFieldOwner = Literal["metadata", "battle_result", "salmon_result"]
MetadataValueKind = Literal["enum", "datetime", "rate", "int", "weapon_slots"]


@dataclass(frozen=True)
class MetadataFieldDefinition:
    """録画メタデータのフィールド定義。"""

    key: str
    category: MetadataFieldCategory
    owner: MetadataFieldOwner
    attr_name: str
    value_kind: MetadataValueKind
    editable: bool = True
    required_for_result: bool = False
    enum_type: type[Enum] | None = None

    def __post_init__(self) -> None:
        if self.value_kind == "enum" and self.enum_type is None:
            raise ValueError(f"{self.key} requires enum_type")


COMMON_METADATA_FIELD_DEFINITIONS: tuple[MetadataFieldDefinition, ...] = (
    MetadataFieldDefinition(
        key="game_mode",
        category="common",
        owner="metadata",
        attr_name="game_mode",
        value_kind="enum",
        enum_type=GameMode,
        editable=True,
    ),
    MetadataFieldDefinition(
        key="started_at",
        category="common",
        owner="metadata",
        attr_name="started_at",
        value_kind="datetime",
        editable=True,
    ),
    MetadataFieldDefinition(
        key="rate",
        category="common",
        owner="metadata",
        attr_name="rate",
        value_kind="rate",
        editable=True,
    ),
    MetadataFieldDefinition(
        key="judgement",
        category="common",
        owner="metadata",
        attr_name="judgement",
        value_kind="enum",
        enum_type=Judgement,
        editable=True,
    ),
    MetadataFieldDefinition(
        key="allies",
        category="common",
        owner="metadata",
        attr_name="allies",
        value_kind="weapon_slots",
        editable=True,
    ),
    MetadataFieldDefinition(
        key="enemies",
        category="common",
        owner="metadata",
        attr_name="enemies",
        value_kind="weapon_slots",
        editable=True,
    ),
)


BATTLE_METADATA_FIELD_DEFINITIONS: tuple[MetadataFieldDefinition, ...] = (
    MetadataFieldDefinition(
        key="match",
        category="battle",
        owner="battle_result",
        attr_name="match",
        value_kind="enum",
        enum_type=Match,
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="rule",
        category="battle",
        owner="battle_result",
        attr_name="rule",
        value_kind="enum",
        enum_type=Rule,
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="stage",
        category="battle",
        owner="battle_result",
        attr_name="stage",
        value_kind="enum",
        enum_type=Stage,
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="kill",
        category="battle",
        owner="battle_result",
        attr_name="kill",
        value_kind="int",
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="death",
        category="battle",
        owner="battle_result",
        attr_name="death",
        value_kind="int",
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="special",
        category="battle",
        owner="battle_result",
        attr_name="special",
        value_kind="int",
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="gold_medals",
        category="battle",
        owner="battle_result",
        attr_name="gold_medals",
        value_kind="int",
        editable=True,
    ),
    MetadataFieldDefinition(
        key="silver_medals",
        category="battle",
        owner="battle_result",
        attr_name="silver_medals",
        value_kind="int",
        editable=True,
    ),
)


SALMON_METADATA_FIELD_DEFINITIONS: tuple[MetadataFieldDefinition, ...] = (
    MetadataFieldDefinition(
        key="stage",
        category="salmon",
        owner="salmon_result",
        attr_name="stage",
        value_kind="enum",
        enum_type=Stage,
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="hazard",
        category="salmon",
        owner="salmon_result",
        attr_name="hazard",
        value_kind="int",
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="golden_egg",
        category="salmon",
        owner="salmon_result",
        attr_name="golden_egg",
        value_kind="int",
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="power_egg",
        category="salmon",
        owner="salmon_result",
        attr_name="power_egg",
        value_kind="int",
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="rescue",
        category="salmon",
        owner="salmon_result",
        attr_name="rescue",
        value_kind="int",
        editable=True,
        required_for_result=True,
    ),
    MetadataFieldDefinition(
        key="rescued",
        category="salmon",
        owner="salmon_result",
        attr_name="rescued",
        value_kind="int",
        editable=True,
        required_for_result=True,
    ),
)


METADATA_FIELD_DEFINITIONS: tuple[MetadataFieldDefinition, ...] = (
    COMMON_METADATA_FIELD_DEFINITIONS
    + BATTLE_METADATA_FIELD_DEFINITIONS
    + SALMON_METADATA_FIELD_DEFINITIONS
)

COMMON_METADATA_FIELDS: frozenset[str] = frozenset(
    field.key for field in COMMON_METADATA_FIELD_DEFINITIONS
)
BATTLE_METADATA_FIELDS: frozenset[str] = frozenset(
    field.key for field in BATTLE_METADATA_FIELD_DEFINITIONS
)
SALMON_METADATA_FIELDS: frozenset[str] = frozenset(
    field.key for field in SALMON_METADATA_FIELD_DEFINITIONS
)
EDITABLE_METADATA_FIELDS: frozenset[str] = frozenset(
    field.key for field in METADATA_FIELD_DEFINITIONS if field.editable
)
RECORDED_METADATA_PATCH_FIELDS: frozenset[str] = frozenset(
    field.key
    for field in METADATA_FIELD_DEFINITIONS
    if field.editable
    and field.category != "salmon"
    and field.key not in {"game_mode", "started_at"}
)

BATTLE_RESULT_REQUIRED_FIELDS: tuple[str, ...] = tuple(
    field.key
    for field in BATTLE_METADATA_FIELD_DEFINITIONS
    if field.required_for_result
)
SALMON_RESULT_REQUIRED_FIELDS: tuple[str, ...] = tuple(
    field.key
    for field in SALMON_METADATA_FIELD_DEFINITIONS
    if field.required_for_result
)

_RESULT_FIELD_DEFINITIONS: dict[
    GameMode, tuple[MetadataFieldDefinition, ...]
] = {
    GameMode.BATTLE: BATTLE_METADATA_FIELD_DEFINITIONS,
    GameMode.SALMON: SALMON_METADATA_FIELD_DEFINITIONS,
}


def get_result_field_definitions(
    game_mode: GameMode,
) -> tuple[MetadataFieldDefinition, ...]:
    """ゲームモードに対応する結果フィールド定義を返す。"""

    return _RESULT_FIELD_DEFINITIONS.get(game_mode, ())


def has_required_fields(
    data: Mapping[str, object], required_fields: tuple[str, ...]
) -> bool:
    """必須フィールドがすべて埋まっているかを返す。"""

    for field in required_fields:
        if field not in data:
            return False
        value = data.get(field)
        if value is None:
            return False
        if isinstance(value, str) and not value:
            return False
    return True
