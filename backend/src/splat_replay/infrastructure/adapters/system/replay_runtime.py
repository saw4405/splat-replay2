"""リプレイ E2E 用に外部デバイスへ到達しないアダプター。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import (
    CaptureDeviceEnumeratorPort,
    EnvironmentPort,
    MicrophoneEnumeratorPort,
    OBSMainOutputCheckResult,
    OBSWebSocketCheckResult,
    PathsPort,
    PowerPort,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)


REPLAY_OBS_WEBSOCKET_HOST = "127.0.0.1"
REPLAY_OBS_WEBSOCKET_PORT = 4455
REPLAY_OBS_WEBSOCKET_PASSWORD = "e2e-only-not-a-real-password"


class ReplaySoftwareChecker:
    """REPLAY の OBS / DistroAV / NDI 存在観測を外部環境から分離する。"""

    def check(self) -> SoftwareCheckResult:
        return SoftwareCheckResult(is_installed=True)


class ReplayOBSConfigurationChecker:
    """OBS の外部保存構成を E2E 専用の固定観測値で照合する。"""

    def check(self) -> OBSMainOutputCheckResult:
        return OBSMainOutputCheckResult(status="enabled")

    def check_websocket(
        self, host: str, port: int, password: str
    ) -> OBSWebSocketCheckResult:
        if host.strip() != REPLAY_OBS_WEBSOCKET_HOST:
            return OBSWebSocketCheckResult(status="unverified")
        if port != REPLAY_OBS_WEBSOCKET_PORT:
            return OBSWebSocketCheckResult(status="port_mismatch")
        if password != REPLAY_OBS_WEBSOCKET_PASSWORD:
            return OBSWebSocketCheckResult(status="password_mismatch")
        return OBSWebSocketCheckResult(status="ready")


class ReplayPathsAdapter(PathsPort):
    """REPLAY の OAuth 検査を E2E 専用 config directory に閉じ込める。"""

    def __init__(
        self, delegate: PathsPort, environment: EnvironmentPort
    ) -> None:
        self._delegate = delegate
        self._environment = environment

    def validate_isolation(self) -> None:
        """設定ファイルの読取前に REPLAY 専用 root 内か確認する。"""
        root_path = self._get_root_path()
        settings_file = self._delegate.get_settings_file()
        if not settings_file.is_absolute():
            raise RuntimeError(
                "REPLAY の設定ファイルは E2E root 内の絶対パスが必要です"
            )

        resolved_root = root_path.resolve()
        resolved_settings_file = settings_file.resolve()
        try:
            resolved_settings_file.relative_to(resolved_root)
        except ValueError as exc:
            raise RuntimeError(
                "REPLAY の設定ファイルは SPLAT_REPLAY_E2E_ROOT 内に必要です"
            ) from exc

    def validate_storage_dir(self, storage_dir: Path) -> None:
        """動画保存先を検証し、REPLAY の書込先を専用 root 内に閉じる。"""
        root_path = self._get_root_path().resolve()
        if not storage_dir.is_absolute():
            raise RuntimeError(
                "REPLAY の動画保存先は E2E root 内の絶対パスが必要です"
            )
        resolved_storage_dir = storage_dir.resolve()
        try:
            resolved_storage_dir.relative_to(root_path)
        except ValueError as exc:
            raise RuntimeError(
                "REPLAY の動画保存先は SPLAT_REPLAY_E2E_ROOT 内に必要です"
            ) from exc

    def get_settings_file(self) -> Path:
        self.validate_isolation()
        return self._delegate.get_settings_file()

    def get_config_dir(self) -> Path:
        root_path = self._get_root_path().resolve()
        config_dir = (root_path / "config").resolve()
        try:
            config_dir.relative_to(root_path)
        except ValueError as exc:
            raise RuntimeError(
                "REPLAY の config directory は SPLAT_REPLAY_E2E_ROOT 内に必要です"
            ) from exc
        return config_dir

    def _get_root_path(self) -> Path:
        root_dir = self._environment.get("SPLAT_REPLAY_E2E_ROOT")
        if not root_dir:
            raise RuntimeError("REPLAY には SPLAT_REPLAY_E2E_ROOT が必要です")
        root_path = Path(root_dir)
        if not root_path.is_absolute():
            raise RuntimeError(
                "SPLAT_REPLAY_E2E_ROOT は絶対パスである必要があります"
            )
        return root_path

    def get_thumbnail_assets_dir(self) -> Path:
        return self._delegate.get_thumbnail_assets_dir()

    def get_thumbnail_asset(self, filename: str) -> Path:
        return self._delegate.get_thumbnail_asset(filename)


class ReplayCaptureDeviceEnumerator(CaptureDeviceEnumeratorPort):
    """リプレイ実行では実機キャプチャデバイスを列挙しない。"""

    def list_video_devices(self) -> list[str]:
        return []


class ReplayMicrophoneEnumerator(MicrophoneEnumeratorPort):
    """リプレイ実行では実機マイクを列挙しない。"""

    def list_microphones(self) -> list[str]:
        return []

    def find_microphone_index(self, device_name: str) -> int | None:
        del device_name
        return None


class ReplayPower(PowerPort):
    """リプレイ実行で OS の電源状態を変更しない。"""

    async def sleep(self) -> None:
        raise RuntimeError(
            "SPLAT_REPLAY_RUNTIME_PROFILE=replay では電源操作を実行できません"
        )
