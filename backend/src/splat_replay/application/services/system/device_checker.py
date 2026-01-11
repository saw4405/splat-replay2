"""環境初期化サービス。"""

from __future__ import annotations

import asyncio
import time

from splat_replay.application.interfaces import (
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CaptureDeviceSettingsView,
    LoggerPort,
    MicrophoneEnumeratorPort,
)


class DeviceChecker:
    """キャプチャデバイスの接続待機を担当するサービス。"""

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
        """キャプチャデバイスが接続されているか確認する。"""
        return self.device.is_connected()

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None:
        """キャプチャデバイス設定を更新する。"""
        self.device.update_settings(settings)
        self.logger.info(
            "キャプチャデバイス設定を更新しました",
            device_name=settings.name,
        )

    def list_video_capture_devices(self) -> list[str]:
        """ビデオキャプチャデバイス一覧を取得する。"""
        devices = self._enumerator.list_video_devices()
        self.logger.info("Video capture devices listed", count=len(devices))
        return devices

    def list_microphone_devices(self) -> list[str]:
        """マイクデバイス一覧を取得する。"""
        devices = self._microphone_enumerator.list_microphones()
        self.logger.info("Microphone devices listed", count=len(devices))
        return devices

    async def wait_for_device_connection(
        self, timeout: float | None = None
    ) -> bool:
        """キャプチャデバイスの接続を待機する。"""
        start_time = time.time()
        while not await asyncio.to_thread(self.device.is_connected):
            elapsed = time.time() - start_time
            if timeout is not None and elapsed > timeout:
                self.logger.error(
                    "キャプチャデバイスが見つかりません (timeout)"
                )
                return False
            await asyncio.sleep(0.5)
        self.logger.info("キャプチャデバイスが接続されました")
        return True
