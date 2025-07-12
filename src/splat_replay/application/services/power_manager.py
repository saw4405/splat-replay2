"""電源管理サービス。"""

from __future__ import annotations

from splat_replay.application.interfaces import PowerPort
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.shared.logger import get_logger


class PowerManager:
    """PC の電源操作を担当するサービス。"""

    def __init__(self, power: PowerPort, sm: StateMachine) -> None:
        self.power = power
        self.sm = sm
        self.logger = get_logger()

    def sleep(self) -> None:
        self.logger.info("PC スリープ")
        self.sm.handle(Event.SLEEP)
        self.power.sleep()
