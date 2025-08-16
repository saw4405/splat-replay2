"""電源管理サービス。"""

from __future__ import annotations

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import PowerPort
from splat_replay.shared.config import PCSettings


class PowerManager:
    """PC の電源操作を担当するサービス。"""

    def __init__(
        self,
        power: PowerPort,
        settings: PCSettings,
        logger: BoundLogger,
    ) -> None:
        self.power = power
        self.logger = logger
        self.settings = settings

    def sleep(self) -> None:
        if not self.settings.sleep_after_finish:
            self.logger.info("PC スリープは無効化されています")
            return

        self.logger.info("PC スリープ")
        self.power.sleep()
