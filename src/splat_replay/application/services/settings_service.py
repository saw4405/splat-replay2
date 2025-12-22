from __future__ import annotations

from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    NotRequired,
    Required,
    TypedDict,
    Union,
    cast,
)

from pydantic import BaseModel, SecretStr

from splat_replay.shared import paths
from splat_replay.shared.config.app import AppSettings, SECTION_CLASSES

# PyInstaller環境での無限再帰を避けるため、再帰的型定義をAnyで置換
PrimitiveValue = Union[str, int, float, bool, List[str]]
# 後方互換性のため型エイリアスは維持するが、実質Anyとして扱う
# CompositeFieldValue = Dict[str, "FieldValue"]  # 循環参照のため無効化
# FieldValue = Union[PrimitiveValue, CompositeFieldValue]  # 循環参照のため無効化
CompositeFieldValue = Dict[str, Any]
FieldValue = Any  # PyInstallerでの問題を回避


class SettingFieldData(TypedDict):
    id: Required[str]
    label: Required[str]
    description: Required[str]
    type: Required[str]
    recommended: Required[bool]
    value: NotRequired[Any]  # FieldValueをAnyに変更
    choices: NotRequired[List[str]]
    children: NotRequired[List["SettingFieldData"]]


class SettingSectionData(TypedDict):
    id: Required[str]
    label: Required[str]
    fields: Required[List[SettingFieldData]]


class SectionUpdate(TypedDict):
    id: str
    values: Dict[str, Any]  # FieldValueをAnyに変更


class SettingsServiceError(Exception):
    """Base exception for settings service errors."""


class UnknownSettingsSectionError(SettingsServiceError):
    """Raised when a requested settings section does not exist."""

    def __init__(self, section_id: str) -> None:
        super().__init__(f"Unknown settings section: {section_id}")
        self.section_id = section_id


class UnknownSettingsFieldError(SettingsServiceError):
    """Raised when a requested settings field does not exist."""

    def __init__(self, section_id: str, field_id: str) -> None:
        super().__init__(f"Unknown settings field: {section_id}.{field_id}")
        self.section_id = section_id
        self.field_id = field_id


class SettingsService:
    """Application service that exposes settings metadata and persistence."""

    def __init__(self, settings_path: Path | None = None) -> None:
        self._settings_path = settings_path or paths.SETTINGS_FILE

    def fetch_sections(self) -> List[SettingSectionData]:
        """Return all settings sections with field metadata and current values."""
        settings = AppSettings.load_from_toml(self._settings_path)
        structure = AppSettings.get_setting_structure()

        sections: List[SettingSectionData] = []
        for section_id, section_meta in structure.items():
            # get_setting_structure()が返す動的メタデータ構造のためAnyを使用
            section_meta_dict = cast(Dict[str, Any], section_meta)
            section_label = str(section_meta_dict["display"])
            section_model = getattr(settings, section_id)
            if not isinstance(section_model, BaseModel):
                raise SettingsServiceError(
                    f"Settings section '{section_id}' is not a Pydantic model"
                )

            fields = self._build_fields(type(section_model), section_model)
            sections.append(
                SettingSectionData(
                    id=section_id,
                    label=section_label,
                    fields=fields,
                )
            )
        return sections

    def update_sections(self, updates: List[SectionUpdate]) -> None:
        """Persist provided settings section updates to the TOML settings file."""
        if not updates:
            return

        settings = AppSettings.load_from_toml(self._settings_path)

        for section in updates:
            section_id = section["id"]
            section_cls = SECTION_CLASSES.get(section_id)
            if section_cls is None:
                raise UnknownSettingsSectionError(section_id)

            current_section = getattr(settings, section_id)
            if not isinstance(current_section, BaseModel):
                raise SettingsServiceError(
                    f"Settings section '{section_id}' is not a Pydantic model"
                )

            merged = self._merge_section_values(
                current_section, section["values"], section_id
            )
            setattr(settings, section_id, section_cls(**merged))

        settings.save_to_toml(self._settings_path)

    def _build_fields(
        self,
        model_cls: type[BaseModel],
        model_value: BaseModel,
    ) -> List[SettingFieldData]:
        fields: List[SettingFieldData] = []

        for field_name, model_field in model_cls.__fields__.items():
            label = model_field.field_info.title or field_name
            description = model_field.field_info.description or ""
            recommended = bool(
                model_field.field_info.extra.get("recommended", False)
            )

            field_type, choices = AppSettings._ui_type_of(model_field)

            attribute_value = getattr(model_value, field_name)

            if isinstance(attribute_value, BaseModel):
                child_fields = self._build_fields(
                    type(attribute_value),
                    attribute_value,
                )
                field_data: SettingFieldData = {
                    "id": field_name,
                    "label": label,
                    "description": description,
                    "type": "group",
                    "recommended": recommended,
                    "children": child_fields,
                    "value": self._group_value_from_children(child_fields),
                }
                fields.append(field_data)
                continue

            serialized_value = self._serialize_value(attribute_value)
            field_data = SettingFieldData(
                id=field_name,
                label=label,
                description=description,
                type=field_type,
                recommended=recommended,
            )
            if choices:
                field_data["choices"] = list(choices)

            field_data["value"] = serialized_value
            fields.append(field_data)

        return fields

    def _group_value_from_children(
        self, children: List[SettingFieldData]
    ) -> Dict[str, Any]:  # CompositeFieldValue = Dict[str, Any]
        group_value: Dict[str, Any] = {}
        for child in children:
            child_id = child["id"]
            if child["type"] == "group":
                nested_children = child.get("children", [])
                group_value[child_id] = self._group_value_from_children(
                    nested_children
                )
            else:
                value = child.get("value")
                if isinstance(value, dict):
                    group_value[child_id] = value
                elif value is None:
                    group_value[child_id] = ""
                else:
                    group_value[child_id] = value
        return group_value

    def _serialize_value(self, value: object) -> Any:
        """Convert a Pydantic model field value to JSON-serializable format.

        # PyInstaller環境での問題を回避するためAnyを使用
        """
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, list):
            return [self._serialize_list_item(item) for item in value]
        if isinstance(value, (str, int, float, bool)):
            return value
        return None

    def _serialize_list_item(self, item: object) -> str:
        if isinstance(item, SecretStr):
            return item.get_secret_value()
        return str(item)

    def _merge_section_values(
        self,
        current: BaseModel,
        updates: Mapping[str, Any],  # FieldValueをAnyに変更
        section_path: str,
    ) -> Dict[str, object]:
        merged: Dict[str, object] = current.dict()
        for field_id, new_value in updates.items():
            if not hasattr(current, field_id):
                raise UnknownSettingsFieldError(section_path, field_id)

            existing_value = getattr(current, field_id)
            if isinstance(existing_value, BaseModel):
                if not isinstance(new_value, dict):
                    raise UnknownSettingsFieldError(section_path, field_id)
                nested_updates: Mapping[str, Any] = (
                    new_value  # FieldValueをAnyに変更
                )
                merged[field_id] = self._merge_section_values(
                    existing_value,
                    nested_updates,
                    f"{section_path}.{field_id}",
                )
            else:
                merged[field_id] = new_value

        return merged


__all__ = [
    "CompositeFieldValue",
    "FieldValue",
    "PrimitiveValue",
    "SectionUpdate",
    "SettingFieldData",
    "SettingSectionData",
    "SettingsService",
    "SettingsServiceError",
    "UnknownSettingsFieldError",
    "UnknownSettingsSectionError",
]
