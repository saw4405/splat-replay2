"""録画メタデータの serialize / parse 支援。"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from splat_replay.domain.models import (
    BattleResult,
    RecordingMetadata,
    SalmonResult,
)
from splat_replay.domain.models.rate import RateBase

from .schema import (
    BATTLE_METADATA_FIELD_DEFINITIONS,
    COMMON_METADATA_FIELD_DEFINITIONS,
    MetadataFieldDefinition,
    SALMON_METADATA_FIELD_DEFINITIONS,
)

MetadataValue = str | int | list[str] | None
MISSING: Final = object()


def serialize_metadata_value(value: object) -> MetadataValue:
    """JSON 保存・イベント配信用に値を serialize する。"""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, RateBase):
        return str(value)
    if isinstance(value, tuple):
        return [item if isinstance(item, str) else str(item) for item in value]
    if isinstance(value, list):
        return [item if isinstance(item, str) else str(item) for item in value]
    if hasattr(value, "name") and isinstance(getattr(value, "name"), str):
        return getattr(value, "name")
    if isinstance(value, (str, int)):
        return value
    return str(value)


def recording_metadata_to_dict(
    metadata: RecordingMetadata,
) -> dict[str, MetadataValue]:
    """RecordingMetadata を JSON 互換辞書へ変換する。"""

    payload: dict[str, MetadataValue] = {}
    for field in COMMON_METADATA_FIELD_DEFINITIONS:
        payload[field.key] = serialize_metadata_value(
            getattr(metadata, field.attr_name)
        )

    result = metadata.result
    result_fields: tuple[MetadataFieldDefinition, ...] = ()
    if isinstance(result, BattleResult):
        result_fields = BATTLE_METADATA_FIELD_DEFINITIONS
    elif isinstance(result, SalmonResult):
        result_fields = SALMON_METADATA_FIELD_DEFINITIONS

    for field in result_fields:
        payload[field.key] = serialize_metadata_value(
            getattr(result, field.attr_name)
        )

    return payload


def parse_metadata_field_update(
    field: MetadataFieldDefinition, raw: object
) -> object:
    """更新入力をドメイン値へ変換する。"""

    if field.value_kind == "enum":
        if not isinstance(raw, str) or field.enum_type is None:
            return MISSING
        try:
            return field.enum_type[raw]
        except Exception:
            return MISSING

    if field.value_kind == "datetime":
        if not isinstance(raw, str):
            return MISSING
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            return MISSING

    if field.value_kind == "rate":
        if not isinstance(raw, str):
            return MISSING
        try:
            return RateBase.create(raw)
        except Exception:
            return MISSING

    if field.value_kind == "int":
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str):
            try:
                return int(raw)
            except Exception:
                return MISSING
        return MISSING

    if field.value_kind == "weapon_slots":
        if not isinstance(raw, (list, tuple)):
            return MISSING
        if len(raw) != 4:
            return MISSING
        if not all(isinstance(item, str) for item in raw):
            return MISSING
        return (raw[0], raw[1], raw[2], raw[3])

    return MISSING


def parse_optional_metadata_field(
    field: MetadataFieldDefinition, raw: object
) -> object | None:
    """保存済みデータの読み込み用に値を変換する。"""

    if raw is None:
        return None
    parsed = parse_metadata_field_update(field, raw)
    if parsed is MISSING:
        return None
    return parsed
