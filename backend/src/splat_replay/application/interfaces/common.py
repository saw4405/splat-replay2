"""Common cross-cutting concern ports."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from splat_replay.application.interfaces.data import (
    BehaviorSettingsView,
    CaptureDeviceSettingsView,
    OBSSettingsView,
    UploadSettingsView,
    VideoEditSettingsView,
)


class LoggerPort(Protocol):
    """Application layer logging abstraction."""

    def debug(self, event: str, **kw: object) -> None: ...

    def info(self, event: str, **kw: object) -> None: ...

    def warning(self, event: str, **kw: object) -> None: ...

    def error(self, event: str, **kw: object) -> None: ...

    def exception(self, event: str, **kw: object) -> None: ...


class ClockPort(Protocol):
    """Abstraction for the current capture timeline clock."""

    def now(self) -> float: ...


class ConfigPort(Protocol):
    """Configuration access abstraction."""

    def get_behavior_settings(self) -> BehaviorSettingsView: ...

    def get_upload_settings(self) -> UploadSettingsView: ...

    def get_video_edit_settings(self) -> VideoEditSettingsView: ...

    def get_obs_settings(self) -> OBSSettingsView: ...

    def save_obs_websocket_password(self, password: str) -> None: ...

    def get_capture_device_settings(self) -> CaptureDeviceSettingsView: ...

    def save_capture_device_name(self, device_name: str) -> None: ...

    def save_capture_device_binding(
        self,
        device_name: str,
        hardware_id: str | None = None,
        location_path: str | None = None,
        parent_instance_id: str | None = None,
    ) -> None: ...

    def save_upload_privacy_status(self, privacy_status: str) -> None: ...


class PathsPort(Protocol):
    """Filesystem path lookup abstraction."""

    def get_settings_file(self) -> Path: ...

    def get_config_dir(self) -> Path: ...

    def get_thumbnail_assets_dir(self) -> Path: ...

    def get_thumbnail_asset(self, filename: str) -> Path: ...


class FileSystemPort(Protocol):
    """Filesystem interaction abstraction."""

    def exists(self, path: Path) -> bool: ...

    def is_file(self, path: Path) -> bool: ...

    def is_dir(self, path: Path) -> bool: ...

    def read_bytes(self, path: Path) -> bytes: ...

    def write_text(
        self, path: Path, content: str, encoding: str = "utf-8"
    ) -> None: ...

    def write_bytes(self, path: Path, data: bytes) -> None: ...

    def unlink(self, path: Path, *, missing_ok: bool = True) -> None: ...
