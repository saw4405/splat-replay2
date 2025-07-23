"""電源管理サービス。"""

from __future__ import annotations

from structlog.stdlib import BoundLogger
from splat_replay.shared.config import PCSettings
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.application.interfaces import PowerPort


class PowerManager:
    """PC の電源操作を担当するサービス。"""

    def __init__(
        self,
        power: PowerPort,
        sm: StateMachine,
        settings: PCSettings,
        logger: BoundLogger,
    ) -> None:
        self.power = power
        self.sm = sm
        self.logger = logger
        self.settings = settings

    def sleep(self) -> None:
        if not self.settings.sleep_after_finish:
            self.logger.info("PC スリープは無効化されています")
            return

        self.logger.info("PC スリープ")
        self.sm.handle(Event.SLEEP)
        self.power.sleep()
