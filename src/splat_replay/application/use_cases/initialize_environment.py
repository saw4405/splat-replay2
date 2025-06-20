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

    def execute(self) -> None:
        """接続確認と OBS 起動・仮想カメラ開始を行う。"""
        if not self.device.is_connected():
            self.logger.error("キャプチャデバイス未接続")
            raise RuntimeError("キャプチャデバイスが見つかりません")

        if not self.obs.is_running():
            self.logger.info("OBS 起動")
            self.obs.launch()

        self.logger.info("仮想カメラ開始")
        self.obs.start_virtual_camera()
        self.sm.handle(Event.INITIALIZED)
