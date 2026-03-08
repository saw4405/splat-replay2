"""メタデータの単一定義源。"""

from .codec import (
    recording_metadata_to_dict,
    serialize_metadata_value,
)
from .schema import (
    BATTLE_METADATA_FIELDS,
    BATTLE_METADATA_FIELD_DEFINITIONS,
    BATTLE_RESULT_REQUIRED_FIELDS,
    COMMON_METADATA_FIELDS,
    COMMON_METADATA_FIELD_DEFINITIONS,
    EDITABLE_METADATA_FIELDS,
    METADATA_FIELD_DEFINITIONS,
    RECORDED_METADATA_PATCH_FIELDS,
    SALMON_METADATA_FIELDS,
    SALMON_METADATA_FIELD_DEFINITIONS,
    SALMON_RESULT_REQUIRED_FIELDS,
    MetadataFieldDefinition,
    get_result_field_definitions,
    has_required_fields,
)

__all__ = [
    "BATTLE_METADATA_FIELDS",
    "BATTLE_METADATA_FIELD_DEFINITIONS",
    "BATTLE_RESULT_REQUIRED_FIELDS",
    "COMMON_METADATA_FIELDS",
    "COMMON_METADATA_FIELD_DEFINITIONS",
    "EDITABLE_METADATA_FIELDS",
    "METADATA_FIELD_DEFINITIONS",
    "RECORDED_METADATA_PATCH_FIELDS",
    "SALMON_METADATA_FIELDS",
    "SALMON_METADATA_FIELD_DEFINITIONS",
    "SALMON_RESULT_REQUIRED_FIELDS",
    "MetadataFieldDefinition",
    "get_result_field_definitions",
    "has_required_fields",
    "recording_metadata_to_dict",
    "serialize_metadata_value",
]
