"""Settings repository adapter backed by AppSettings TOML."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, cast

from pydantic import BaseModel, SecretStr
from splat_replay.application.interfaces import (
    SectionUpdate,
    SettingFieldData,
    SettingSectionData,
    SettingsRepositoryPort,
)
from splat_replay.application.services.common.settings_service import (
    SettingsServiceError,
    UnknownSettingsFieldError,
    UnknownSettingsSectionError,
)
from splat_replay.domain.config import SECTION_CLASSES
from splat_replay.infrastructure.config import (
    _ui_type_of,
    get_setting_structure,
    load_settings_from_toml,
    save_settings_to_toml,
)
from splat_replay.infrastructure.filesystem import paths

if TYPE_CHECKING:
    from splat_replay.application.interfaces import CaptureDeviceEnumeratorPort


class TomlSettingsRepository(SettingsRepositoryPort):
    """Persist and load settings metadata via AppSettings."""

    def __init__(
        self,
        settings_path: Path | None = None,
        device_enumerator: CaptureDeviceEnumeratorPort | None = None,
    ) -> None:
        self._settings_path = settings_path or paths.SETTINGS_FILE
        self._device_enumerator = device_enumerator

    def fetch_sections(self) -> List[SettingSectionData]:
        settings = load_settings_from_toml(self._settings_path)
        structure = get_setting_structure()

        sections: List[SettingSectionData] = []
        for section_id, section_meta in structure.items():
            # get_setting_structure() returns dynamic metadata; cast for access.
            section_meta_dict = cast(Dict[str, Any], section_meta)
            section_label = str(section_meta_dict["display"])
            section_model = getattr(settings, section_id)
            if not isinstance(section_model, BaseModel):
                raise SettingsServiceError(
                    f"Settings section '{section_id}' is not a Pydantic model"
                )

            fields = self._build_fields(
                type(section_model), section_model, section_id
            )
            sections.append(
                SettingSectionData(
                    id=section_id,
                    label=section_label,
                    fields=fields,
                )
            )
        return sections

    def update_sections(self, updates: List[SectionUpdate]) -> None:
        if not updates:
            return

        settings = load_settings_from_toml(self._settings_path)

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

        save_settings_to_toml(settings, self._settings_path)

    def _build_fields(
        self,
        model_cls: type[BaseModel],
        model_value: BaseModel,
        section_id: str = "",
        parent_field_id: str = "",
    ) -> List[SettingFieldData]:
        fields: List[SettingFieldData] = []

        for field_name, model_field in model_cls.__fields__.items():
            label = model_field.field_info.title or field_name
            description = model_field.field_info.description or ""
            recommended = bool(
                model_field.field_info.extra.get("recommended", False)
            )

            field_type, choices = _ui_type_of(model_field)

            attribute_value = getattr(model_value, field_name)

            if isinstance(attribute_value, BaseModel):
                child_fields = self._build_fields(
                    type(attribute_value),
                    attribute_value,
                    section_id,
                    field_name,
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

            # キャプチャデバイスの場合は動的に選択肢を追加
            should_add_device_choices = (
                # record.capture_device フィールド
                (section_id == "record" and field_name == "capture_device")
                # capture_device.name フィールド
                or (section_id == "capture_device" and field_name == "name")
                # record グループ内の capture_device.name フィールド
                or (
                    section_id == "record"
                    and parent_field_id == "capture_device"
                    and field_name == "name"
                )
            )

            if (
                should_add_device_choices
                and self._device_enumerator is not None
            ):
                try:
                    devices = self._device_enumerator.list_video_devices()
                    if devices:
                        field_data["type"] = "select"
                        field_data["choices"] = devices
                        # 現在の値がリストにない場合は追加
                        if (
                            isinstance(serialized_value, str)
                            and serialized_value
                            and serialized_value not in devices
                        ):
                            field_data["choices"].append(serialized_value)
                except Exception:
                    # デバイス列挙に失敗した場合はテキスト入力にフォールバック
                    pass

            if choices:
                field_data["choices"] = list(choices)

            field_data["value"] = serialized_value
            fields.append(field_data)

        return fields

    def _group_value_from_children(
        self, children: List[SettingFieldData]
    ) -> Dict[str, Any]:
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
        """Convert a Pydantic model field value to JSON-serializable format."""
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
        updates: Mapping[str, Any],
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
                nested_updates: Mapping[str, Any] = new_value
                merged[field_id] = self._merge_section_values(
                    existing_value,
                    nested_updates,
                    f"{section_path}.{field_id}",
                )
            else:
                merged[field_id] = new_value

        return merged
