"""Cross-cutting concerns の adapter 実装。

Logger / Config / Paths ポートの具象実装を提供。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

from pydantic import SecretStr
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces.common import (
    ConfigPort,
    FileSystemPort,
    LoggerPort,
    PathsPort,
)
from splat_replay.application.interfaces.data import (
    BehaviorSettingsView,
    CaptureDeviceSettingsView,
    OBSSettingsView,
    PrivacyStatus,
    UploadSettingsView,
    VideoEditSettingsView,
)
from splat_replay.application.interfaces.system import EnvironmentPort
from splat_replay.domain.config import (
    AppSettings,
    CaptureDeviceSettings,
    OBSSettings,
    UploadSettings,
)
from splat_replay.infrastructure.config import (
    load_settings_from_toml,
    save_settings_to_toml,
)
from splat_replay.infrastructure.filesystem import paths
from splat_replay.infrastructure.logging import get_logger


class StructlogLoggerAdapter(LoggerPort):
    """Structlog を使用した LoggerPort の実装。"""

    def __init__(self) -> None:
        self._logger: BoundLogger = get_logger()

    def debug(self, event: str, **kw: object) -> None:
        self._logger.debug(event, **kw)

    def info(self, event: str, **kw: object) -> None:
        self._logger.info(event, **kw)

    def warning(self, event: str, **kw: object) -> None:
        self._logger.warning(event, **kw)

    def error(self, event: str, **kw: object) -> None:
        self._logger.error(event, **kw)

    def exception(self, event: str, **kw: object) -> None:
        self._logger.exception(event, **kw)


class TomlConfigAdapter(ConfigPort):
    """TOML ファイルを使用した ConfigPort の実装。"""

    def __init__(self, settings_path: Path | None = None) -> None:
        self._settings_path = settings_path or paths.SETTINGS_FILE
        self._settings: AppSettings | None = None

    def _load_settings(self) -> AppSettings:
        self._settings = load_settings_from_toml(self._settings_path)
        return self._settings

    def get_behavior_settings(self) -> BehaviorSettingsView:
        # shared.config の具象型は Protocol を構造的に満たしている
        return cast(BehaviorSettingsView, self._load_settings().behavior)

    def get_upload_settings(self) -> UploadSettingsView:
        return cast(UploadSettingsView, self._load_settings().upload)

    def get_video_edit_settings(self) -> VideoEditSettingsView:
        return cast(VideoEditSettingsView, self._load_settings().video_edit)

    def get_obs_settings(self) -> OBSSettingsView:
        return cast(OBSSettingsView, self._load_settings().obs)

    def get_capture_device_settings(self) -> CaptureDeviceSettingsView:
        return cast(
            CaptureDeviceSettingsView, self._load_settings().capture_device
        )

    def save_obs_websocket_password(self, password: str) -> None:
        settings = self._load_settings()
        current = settings.obs
        settings.obs = OBSSettings(
            websocket_host=current.websocket_host,
            websocket_port=current.websocket_port,
            websocket_password=SecretStr(password),
            executable_path=current.executable_path,
        )
        save_settings_to_toml(settings, self._settings_path)
        self._settings = settings

    def save_capture_device_name(self, device_name: str) -> None:
        settings = self._load_settings()
        settings.capture_device = CaptureDeviceSettings(name=device_name)
        save_settings_to_toml(settings, self._settings_path)
        self._settings = settings

    def save_upload_privacy_status(self, privacy_status: str) -> None:
        settings = self._load_settings()
        current = settings.upload
        settings.upload = UploadSettings(
            privacy_status=cast(PrivacyStatus, privacy_status),
            tags=current.tags,
            playlist_id=current.playlist_id,
            caption_name=current.caption_name,
        )
        save_settings_to_toml(settings, self._settings_path)
        self._settings = settings


class FileSystemPathsAdapter(PathsPort):
    """ファイルシステムを使用した PathsPort の実装。"""

    def get_settings_file(self) -> Path:
        return paths.SETTINGS_FILE

    def get_config_dir(self) -> Path:
        return paths.CONFIG_DIR

    def get_thumbnail_assets_dir(self) -> Path:
        return paths.THUMBNAIL_ASSETS_DIR

    def get_thumbnail_asset(self, filename: str) -> Path:
        return paths.thumbnail_asset(filename)


class LocalFileSystemAdapter(FileSystemPort):
    """ローカルファイルシステムを使用した FileSystemPort の実装。"""

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()

    def write_text(
        self, path: Path, content: str, encoding: str = "utf-8"
    ) -> None:
        path.write_text(content, encoding=encoding)

    def write_bytes(self, path: Path, data: bytes) -> None:
        path.write_bytes(data)

    def unlink(self, path: Path, *, missing_ok: bool = True) -> None:
        path.unlink(missing_ok=missing_ok)


class ProcessEnvironmentAdapter(EnvironmentPort):
    """プロセス環境変数を使用した EnvironmentPort の実装。"""

    def get(self, name: str, default: str | None = None) -> str | None:
        return os.environ.get(name, default)

    def set(self, name: str, value: str) -> None:
        os.environ[name] = value
