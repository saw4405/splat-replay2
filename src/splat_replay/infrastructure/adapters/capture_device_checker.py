"""キャプチャデバイス接続確認アダプタ。"""

from __future__ import annotations

import sys

from splat_replay.shared.config import CaptureDeviceSettings
from splat_replay.shared.logger import get_logger
from splat_replay.application.interfaces import CaptureDevicePort

logger = get_logger()


class CaptureDeviceChecker(CaptureDevicePort):
    """キャプチャデバイスの接続状態を確認する。"""

    def __init__(self, settings: CaptureDeviceSettings) -> None:
        """設定を受け取り初期化する。"""

        self.device_name = settings.name

    def is_connected(self) -> bool:
        """デバイスが接続済みかを返す。"""

        # Windows 以外では実機での確認ができないため常に接続済みとみなす
        if sys.platform != "win32":
            logger.warning("Windowsでないため、チェックをスキップします")
            return True

        try:  # pragma: no cover - OS 依存
            import win32com.client

            wmi = win32com.client.GetObject("winmgmts:")
            devices = wmi.InstancesOf("Win32_PnPEntity")
        except Exception as e:  # pragma: no cover - 実機依存
            logger.warning("キャプチャデバイス確認失敗", error=str(e))
            return False

        return any(str(device.Name) == self.device_name for device in devices)
