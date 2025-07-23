"""環境初期化サービス。"""

from __future__ import annotations

import asyncio
import time

from structlog.stdlib import BoundLogger
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.application.interfaces import (
    CaptureDevicePort,
    OBSControlPort,
)


class EnvironmentInitializer:
    """キャプチャデバイス接続確認と OBS 起動を担当するサービス。"""

    def __init__(
        self,
        device: CaptureDevicePort,
        obs: OBSControlPort,
        sm: StateMachine,
        logger: BoundLogger,
    ) -> None:
        self.device = device
        self.obs = obs
        self.sm = sm
        self.logger = logger

    async def wait_for_device(self, timeout: float | None = None) -> bool:
        """キャプチャデバイスの接続を待機する。"""

        start_time = time.time()
        while not await asyncio.to_thread(self.device.is_connected):
            elapsed = time.time() - start_time
            if timeout is not None and elapsed > timeout:
                return False
            await asyncio.sleep(0.5)
        return True

    async def execute(self, timeout: float | None = None) -> None:
        """接続確認と OBS 起動・仮想カメラ開始を行う。"""
        if not await self.wait_for_device(timeout):
            self.logger.error("キャプチャデバイスが見つかりません (timeout)")
            raise RuntimeError("キャプチャデバイスが見つかりません (timeout)")

        self.sm.handle(Event.DEVICE_CONNECTED)

        if not await asyncio.to_thread(self.obs.is_running):
            self.logger.info("OBS 起動")
            await asyncio.to_thread(self.obs.launch)

        await asyncio.to_thread(self.obs.connect)
        if not await asyncio.to_thread(self.obs.is_connected):
            self.logger.error("OBS WebSocket 接続失敗")
            raise RuntimeError("OBS WebSocket への接続に失敗しました")

        self.logger.info("仮想カメラ開始")
        await asyncio.to_thread(self.obs.start_virtual_camera)
        self.sm.handle(Event.INITIALIZED)
