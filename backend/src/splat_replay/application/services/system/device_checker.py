"""キャプチャーデバイスの接続確認と列挙を担当するサービス。"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from splat_replay.application.interfaces import (
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CaptureDeviceSettingsView,
    LoggerPort,
    MicrophoneEnumeratorPort,
)


class DeviceChecker:
    """キャプチャーデバイスの状態と一覧を扱う。"""

    def __init__(
        self,
        device: CaptureDevicePort,
        enumerator: CaptureDeviceEnumeratorPort,
        microphone_enumerator: MicrophoneEnumeratorPort,
        logger: LoggerPort,
    ) -> None:
        self.device = device
        self._enumerator = enumerator
        self._microphone_enumerator = microphone_enumerator
        self.logger = logger

    def is_connected(self) -> bool:
        """設定したキャプチャーデバイスの接続状態を返す。"""
        return self.device.is_connected()

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None:
        self.device.update_settings(settings)
        self.logger.info(
            "Capture device settings updated", device_name=settings.name
        )

    def list_video_capture_devices(self) -> list[str]:
        devices = self._enumerator.list_video_devices()
        self.logger.info("Video capture devices listed", count=len(devices))
        return devices

    def list_microphone_devices(self) -> list[str]:
        devices = self._microphone_enumerator.list_microphones()
        self.logger.info("Microphone devices listed", count=len(devices))
        return devices

    def find_microphone_index(self, device_name: str) -> Optional[int]:
        return self._microphone_enumerator.find_microphone_index(device_name)

    async def wait_for_device_connection(
        self, timeout: float | None = None
    ) -> bool:
        start_time = time.time()
        while not await asyncio.to_thread(self.is_connected):
            if timeout is not None and time.time() - start_time > timeout:
                self.logger.error(
                    "Capture device did not appear before timeout"
                )
                return False
            await asyncio.sleep(0.5)
        self.logger.info("Capture device connected")
        return True
