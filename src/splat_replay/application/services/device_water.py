"""環境初期化サービス。"""

from __future__ import annotations

import asyncio
import time

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CaptureDevicePort,
)


class DeviceWaiter:
    """キャプチャデバイスの接続待機を担当するサービス。"""

    def __init__(self, device: CaptureDevicePort, logger: BoundLogger) -> None:
        self.device = device
        self.logger = logger

    async def execute(self, timeout: float | None = None) -> bool:
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
