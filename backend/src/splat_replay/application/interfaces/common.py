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
    """ロガーのポート（構造化ログ出力）。

    Application 層は concrete な logger に依存せず、
    このポートを通じてログ出力を行う。
    """

    def debug(self, event: str, **kw: object) -> None:
        """デバッグレベルのログ出力。"""
        ...

    def info(self, event: str, **kw: object) -> None:
        """情報レベルのログ出力。"""
        ...

    def warning(self, event: str, **kw: object) -> None:
        """警告レベルのログ出力。"""
        ...

    def error(self, event: str, **kw: object) -> None:
        """エラーレベルのログ出力。"""
        ...

    def exception(self, event: str, **kw: object) -> None:
        """例外レベルのログ出力。"""
        ...


class ConfigPort(Protocol):
    """設定値取得のポート。

    Application 層は concrete な設定実装に依存せず、
    このポートを通じて設定値を取得する。
    """

    def get_behavior_settings(self) -> BehaviorSettingsView:
        """動作設定を取得。"""
        ...

    def get_upload_settings(self) -> UploadSettingsView:
        """アップロード設定を取得。"""
        ...

    def get_video_edit_settings(self) -> VideoEditSettingsView:
        """動画編集設定を取得。"""
        ...

    def get_obs_settings(self) -> OBSSettingsView:
        """OBS 設定を取得。"""
        ...

    def save_obs_websocket_password(self, password: str) -> None:
        """OBS WebSocketパスワードを保存。"""
        ...

    def get_capture_device_settings(self) -> CaptureDeviceSettingsView:
        """キャプチャデバイス設定を取得。"""
        ...

    def save_capture_device_name(self, device_name: str) -> None:
        """キャプチャデバイス名を保存。"""
        ...

    def save_upload_privacy_status(self, privacy_status: str) -> None:
        """YouTube公開設定を保存。"""
        ...


class PathsPort(Protocol):
    """ファイルパス解決のポート。

    Application 層は concrete なパス実装に依存せず、
    このポートを通じてファイルパスを解決する。
    """

    def get_settings_file(self) -> Path:
        """設定ファイルパスを取得。"""
        ...

    def get_config_dir(self) -> Path:
        """設定ディレクトリパスを取得。"""
        ...

    def get_thumbnail_assets_dir(self) -> Path:
        """サムネイルアセットディレクトリパスを取得。"""
        ...

    def get_thumbnail_asset(self, filename: str) -> Path:
        """サムネイルアセットファイルパスを取得。"""
        ...


class FileSystemPort(Protocol):
    """ファイルシステム操作のポート。"""

    def exists(self, path: Path) -> bool:
        """パスが存在するかを確認。"""
        ...

    def is_file(self, path: Path) -> bool:
        """ファイルかどうかを確認。"""
        ...

    def is_dir(self, path: Path) -> bool:
        """ディレクトリかどうかを確認。"""
        ...

    def read_bytes(self, path: Path) -> bytes:
        """バイナリを読み込む。"""
        ...

    def write_text(
        self, path: Path, content: str, encoding: str = "utf-8"
    ) -> None:
        """テキストを書き込む。"""
        ...

    def write_bytes(self, path: Path, data: bytes) -> None:
        """バイナリを書き込む。"""
        ...

    def unlink(self, path: Path, *, missing_ok: bool = True) -> None:
        """ファイルを削除する。"""
        ...
