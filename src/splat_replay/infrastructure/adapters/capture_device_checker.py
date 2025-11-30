"""キャプチャデバイス接続確認アダプタ。"""

from __future__ import annotations

import sys

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import CaptureDevicePort
from splat_replay.shared.config import CaptureDeviceSettings


class CaptureDeviceChecker(CaptureDevicePort):
    """キャプチャデバイスの接続状態を確認する。"""

    def __init__(
        self,
        settings: CaptureDeviceSettings,
        logger: BoundLogger,
    ) -> None:
        """設定を受け取り初期化する。"""

        self.device_name = settings.name
        self.logger = logger

    def update_settings(self, settings: CaptureDeviceSettings) -> None:
        """設定を更新する。

        Args:
            settings: 新しい設定
        """
        self.device_name = settings.name
        self.logger.info(
            "Capture device settings updated", device_name=settings.name
        )

    def is_connected(self) -> bool:
        """デバイスが接続済みかを返す。"""

        # Windows 以外では実機での確認ができないため常に接続済みとみなす
        if sys.platform != "win32":
            self.logger.warning("Windowsでないため、チェックをスキップします")
            return True

        try:
            import win32com.client

            wmi = win32com.client.GetObject("winmgmts:")
            devices = wmi.InstancesOf("Win32_PnPEntity")
        except Exception as e:
            self.logger.warning("キャプチャデバイス確認失敗", error=str(e))
            return False

        return any(str(device.Name) == self.device_name for device in devices)
