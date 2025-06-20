"""起動時初期化ユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import (
    CaptureDevicePort,
    OBSControlPort,
)
from splat_replay.domain.services.state_machine import Event, StateMachine


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

    def execute(self) -> None:
        """接続確認と OBS 起動・仮想カメラ開始を行う。"""
        if not self.device.is_connected():
            raise RuntimeError("キャプチャデバイスが見つかりません")

        if not self.obs.is_running():
            self.obs.launch()

        self.obs.start_virtual_camera()
        self.sm.handle(Event.INITIALIZED)
