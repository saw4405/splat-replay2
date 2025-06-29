"""起動状態を確認するユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import OBSControlPort
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.shared.logger import get_logger


class CheckInitializationUseCase:
    """OBS の状態から初期化済みか判定する。"""

    def __init__(self, obs: OBSControlPort, sm: StateMachine) -> None:
        self.obs = obs
        self.sm = sm
        self.logger = get_logger()

    def execute(self) -> bool:
        """初期化済みなら状態遷移させて True を返す。"""
        if self.obs.is_running() and self.obs.is_virtual_camera_active():
            self.logger.info("初期化済み")
            self.sm.handle(Event.INITIALIZED)
            return True
        self.logger.info("未初期化")
        return False
