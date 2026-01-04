"""Configuration loaders and savers (infrastructure layer)."""

from __future__ import annotations

import tomllib
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    get_args,
    get_origin,
)

import tomli_w
from pydantic import BaseModel, SecretStr
from pydantic.fields import ModelField

from splat_replay.domain.config import SECTION_CLASSES, AppSettings
from splat_replay.infrastructure.filesystem import paths


def load_settings_from_toml(
    path: Path = paths.SETTINGS_FILE,
    create_if_missing: bool = True,
) -> AppSettings:
    """
    TOML ファイルから設定を読み込む。
    指定ファイルが存在しない場合、create_if_missing=True ならデフォルト値で作成。
    """
    file_existed = path.exists()

    raw: Dict[str, Dict[str, object]] = {}
    if file_existed:
        with path.open("rb") as f:
            raw = tomllib.load(f)

    kwargs: Dict[str, Any] = {}
    for section, section_cls in SECTION_CLASSES.items():
        src_data: Dict[str, object] = raw.get(section, {})
        if src_data:
            kwargs[section] = section_cls(**src_data)
        else:
            kwargs[section] = section_cls()

    settings = AppSettings(**kwargs)

    if not file_existed and create_if_missing:
        path.parent.mkdir(parents=True, exist_ok=True)
        save_settings_to_toml(settings, path)

    return settings


def _convert_for_toml(obj: object) -> object:
    """
    dictやリストの中のSecretStrやPathをstrに変換するヘルパー
    """
    if obj is None:
        return None  # Noneはそのまま返す（後で除外される）
    elif isinstance(obj, SecretStr):
        return obj.get_secret_value()
    elif isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, dict):
        # Noneの値を除外してから変換
        return {
            k: _convert_for_toml(v) for k, v in obj.items() if v is not None
        }
    elif isinstance(obj, list):
        return [_convert_for_toml(v) for v in obj]
    else:
        return obj


def convert_to_serializable_dict(settings: AppSettings) -> Dict[str, object]:
    """AppSettings を TOML 保存用の辞書に変換する。"""
    toml_data: Dict[str, object] = {}

    # 各セクションを辞書形式に変換し、SecretStrやPathをstrへ
    toml_data["behavior"] = _convert_for_toml(settings.behavior.dict())
    toml_data["capture_device"] = _convert_for_toml(
        settings.capture_device.dict()
    )
    toml_data["obs"] = _convert_for_toml(settings.obs.dict())
    toml_data["record"] = _convert_for_toml(settings.record.dict())
    toml_data["speech_transcriber"] = _convert_for_toml(
        settings.speech_transcriber.dict()
    )
    toml_data["storage"] = _convert_for_toml(settings.storage.dict())
    toml_data["video_edit"] = _convert_for_toml(settings.video_edit.dict())
    toml_data["upload"] = _convert_for_toml(settings.upload.dict())

    return toml_data


def save_settings_to_toml(
    settings: AppSettings, path: Path = paths.SETTINGS_FILE
) -> None:
    """設定を TOML ファイルに保存する。"""
    toml_data = convert_to_serializable_dict(settings)

    # TOML ファイルに書き込み
    toml_text = tomli_w.dumps(toml_data)
    path.write_text(toml_text, encoding="utf-8")


def _is_list(field_type: object) -> bool:
    return get_origin(field_type) in (list, List)


def _literal_choices(field_type: object) -> Optional[List[str]]:
    if get_origin(field_type) is Literal:
        return [str(v) for v in get_args(field_type)]
    return None


def _enum_choices(field_type: object) -> Optional[List[str]]:
    try:
        if isinstance(field_type, type) and issubclass(field_type, Enum):
            return [str(m.value) for m in field_type]
    except Exception:
        pass
    return None


def _ui_type_of(field: ModelField) -> Tuple[str, Optional[List[str]]]:
    """UIタイプを推定"""
    t = field.outer_type_

    if _is_list(t):
        return "list", None
    try:
        if issubclass(t, Path):
            return "path", None
        if issubclass(t, bool):
            return "boolean", None
        if issubclass(t, int):
            return "integer", None
        if issubclass(t, float):
            return "float", None
        if issubclass(t, SecretStr):
            return "password", None
        if issubclass(t, str):
            return "text", None
    except Exception:
        pass

    if _enum_choices(t) or _literal_choices(t):
        choices: Optional[List[str]] = field.field_info.extra.get("choices")
        if not choices:
            return "text", None
        return "select", choices

    return "text", None


def get_setting_structure() -> Dict[str, object]:
    """
    AppSettings から GUI 用のメタデータを生成
    {
      section_id: {
        "display": "セクション表示名",
        "fields": {
          field_id: {
            "label": "表示名",
            "help": "詳細説明",
            "type": "UIタイプ",
            "choices": ["選択肢1", "選択肢2", ...] | None,
            "default": 値,
            "recommended": True/False
          }, ...
        }
      }, ...
    }
    """
    result: Dict[str, object] = {}

    for sec_id, sec_field in AppSettings.__fields__.items():
        sec_type = sec_field.type_
        sec_display = (getattr(sec_type, "__doc__", None) or sec_id).strip()

        fields_meta: Dict[str, object] = {}
        if issubclass(sec_type, BaseModel):
            for f_id, f in sec_type.__fields__.items():
                label = f.field_info.title or f_id
                help_text = f.field_info.description or ""
                ui_type, choices = _ui_type_of(f)
                recommended = f.field_info.extra.get("recommended", False)

                default = f.default
                if isinstance(default, SecretStr):
                    default = default.get_secret_value()
                if isinstance(default, Path):
                    default = str(default)

                fields_meta[f_id] = {
                    "label": label,
                    "help": help_text,
                    "type": ui_type,
                    "choices": choices,
                    "default": default,
                    "recommended": recommended,
                }

        result[sec_id] = {"display": sec_display, "fields": fields_meta}

    return result
