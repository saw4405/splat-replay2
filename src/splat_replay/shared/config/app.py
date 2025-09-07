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

from splat_replay.shared.config.behavior import BehaviorSettings
from splat_replay.shared.config.capture_device import CaptureDeviceSettings
from splat_replay.shared.config.obs import OBSSettings
from splat_replay.shared.config.record import RecordSettings
from splat_replay.shared.config.speech_transcriber import (
    SpeechTranscriberSettings,
)
from splat_replay.shared.config.upload import UploadSettings
from splat_replay.shared.config.video_edit import VideoEditSettings
from splat_replay.shared.config.video_storage import VideoStorageSettings

SECTION_CLASSES = {
    "behavior": BehaviorSettings,
    "capture_device": CaptureDeviceSettings,
    "obs": OBSSettings,
    "record": RecordSettings,
    "speech_transcriber": SpeechTranscriberSettings,
    "storage": VideoStorageSettings,
    "video_edit": VideoEditSettings,
    "upload": UploadSettings,
}


class AppSettings(BaseModel):
    """アプリケーション全体の設定。"""

    behavior = BehaviorSettings()
    capture_device = CaptureDeviceSettings()
    obs = OBSSettings()
    record = RecordSettings()
    speech_transcriber = SpeechTranscriberSettings()
    storage = VideoStorageSettings()
    video_edit = VideoEditSettings()
    upload = UploadSettings()

    @classmethod
    def load_from_toml(
        cls,
        path: Path = Path("config/settings.toml"),
        create_if_missing: bool = True,
    ) -> "AppSettings":
        """
        TOML ファイルから設定を読み込む。
        指定ファイルが存在しない場合、create_if_missing=True ならデフォルト値で作成。
        """
        file_existed = path.exists()

        raw: Dict[str, Dict[str, Any]] = {}
        if file_existed:
            with path.open("rb") as f:
                raw = tomllib.load(f)

        kwargs: Dict[str, Any] = {}
        for section, section_cls in SECTION_CLASSES.items():
            src_data: Dict[str, Any] = raw.get(section, {})
            if src_data:
                kwargs[section] = section_cls(**src_data)
            else:
                kwargs[section] = section_cls()

        settings = cls(**kwargs)

        if not file_existed and create_if_missing:
            path.parent.mkdir(parents=True, exist_ok=True)
            settings.save_to_toml(path)

        return settings

    def _convert_for_toml(self, obj: Any) -> Any:
        """
        dictやリストの中のSecretStrやPathをstrに変換するヘルパー
        """
        if isinstance(obj, SecretStr):
            return obj.get_secret_value()
        elif isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_for_toml(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_for_toml(v) for v in obj]
        else:
            return obj

    def convert_to_serializable_dict(self) -> Dict[str, dict]:
        toml_data: Dict[str, dict] = {}

        # 各セクションを辞書形式に変換し、SecretStrやPathをstrへ
        toml_data["behavior"] = self._convert_for_toml(self.behavior.dict())
        toml_data["capture_device"] = self._convert_for_toml(
            self.capture_device.dict()
        )
        toml_data["obs"] = self._convert_for_toml(self.obs.dict())
        toml_data["record"] = self._convert_for_toml(self.record.dict())
        toml_data["speech_transcriber"] = self._convert_for_toml(
            self.speech_transcriber.dict()
        )
        toml_data["storage"] = self._convert_for_toml(self.storage.dict())
        toml_data["video_edit"] = self._convert_for_toml(
            self.video_edit.dict()
        )
        toml_data["upload"] = self._convert_for_toml(self.upload.dict())

        return toml_data

    def save_to_toml(self, path: Path = Path("config/settings.toml")) -> None:
        """設定を TOML ファイルに保存する。"""
        toml_data = self.convert_to_serializable_dict()

        # TOML ファイルに書き込み
        toml_text = tomli_w.dumps(toml_data)
        path.write_text(toml_text, encoding="utf-8")

    @staticmethod
    def _is_list(field_type: Any) -> bool:
        return get_origin(field_type) in (list, List)

    @staticmethod
    def _literal_choices(field_type: Any):
        if get_origin(field_type) is Literal:
            return [str(v) for v in get_args(field_type)]
        return None

    @staticmethod
    def _enum_choices(field_type: Any):
        try:
            if issubclass(field_type, Enum):
                return [str(m.value) for m in field_type]
        except Exception:
            pass
        return None

    @staticmethod
    def _ui_type_of(field: ModelField) -> Tuple[str, Optional[List[str]]]:
        """UIタイプを推定"""
        t = field.outer_type_

        if AppSettings._is_list(t):
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

        if AppSettings._enum_choices(t) or AppSettings._literal_choices(t):
            choices: Optional[List[str]] = field.field_info.extra.get(
                "choices"
            )
            if not choices:
                return "text", None
            return "select", choices

        return "text", None

    @classmethod
    def get_setting_structure(cls) -> Dict[str, Any]:
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
        result: Dict[str, Any] = {}

        for sec_id, sec_field in cls.__fields__.items():
            sec_type = sec_field.type_
            sec_display = (
                getattr(sec_type, "__doc__", None) or sec_id
            ).strip()

            fields_meta: Dict[str, Any] = {}
            if issubclass(sec_type, BaseModel):
                for f_id, f in sec_type.__fields__.items():
                    label = f.field_info.title or f_id
                    help_text = f.field_info.description or ""
                    ui_type, choices = AppSettings._ui_type_of(f)
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
