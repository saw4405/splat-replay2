"""起動時初期化ユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import (
    CaptureDevicePort,
    OBSControlPort,
)
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.shared.logger import get_logger


class InitializeEnvironmentUseCase:
    """キャプチャデバイスと OBS の準備を行う。"""

    def __init__(
        self,
        device: CaptureDevicePort,
        obs: OBSControlPort,
        sm: StateMachine,
    ) -> None:
        self.device = device
        self.obs = obs
        self.sm = sm
        self.logger = get_logger()

    def wait_for_device(self, timeout: float | None = None) -> bool:
        """キャプチャデバイスの接続を待機し、接続結果を返す。アニメーション表示は行わない。"""
        import time

        start_time = time.time()
        while not self.device.is_connected():
            elapsed = time.time() - start_time
            if timeout is not None and elapsed > timeout:
                return False
            time.sleep(0.5)
        return True

    def execute(self, timeout: float | None = None) -> None:
        """接続確認と OBS 起動・仮想カメラ開始を行う。"""
        if not self.wait_for_device(timeout):
            self.logger.error("キャプチャデバイスが見つかりません (timeout)")
            raise RuntimeError("キャプチャデバイスが見つかりません (timeout)")

        if not self.obs.is_running():
            self.logger.info("OBS 起動")
            self.obs.launch()

        self.obs.connect()
        if not self.obs.is_connected():
            self.logger.error("OBS WebSocket 接続失敗")
            raise RuntimeError("OBS WebSocket への接続に失敗しました")

        self.logger.info("仮想カメラ開始")
        self.obs.start_virtual_camera()
        self.sm.handle(Event.INITIALIZED)
