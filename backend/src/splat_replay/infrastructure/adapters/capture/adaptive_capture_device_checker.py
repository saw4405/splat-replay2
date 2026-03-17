from __future__ import annotations

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CaptureDevicePort,
    CaptureDeviceSettingsView,
)
from splat_replay.infrastructure.adapters.capture.capture_device_checker import (
    CaptureDeviceChecker,
)
from splat_replay.infrastructure.test_input import (
    resolve_configured_test_video,
)


class AdaptiveCaptureDeviceChecker(CaptureDevicePort):
    """設定に応じて実機確認と動画ファイル確認を切り替える。"""

    def __init__(
        self,
        settings: CaptureDeviceSettingsView,
        logger: BoundLogger,
    ) -> None:
        self._logger = logger
        self._live_checker = CaptureDeviceChecker(settings, logger)

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None:
        self._live_checker.update_settings(settings)

    def is_connected(self) -> bool:
        try:
            resolved = resolve_configured_test_video()
        except FileNotFoundError:
            return False

        if resolved is not None:
            connected = resolved.selected_path.exists()
            self._logger.debug(
                "動画ファイル入力の接続状態を確認しました",
                connected=connected,
                video_path=str(resolved.selected_path),
            )
            return connected

        return self._live_checker.is_connected()
