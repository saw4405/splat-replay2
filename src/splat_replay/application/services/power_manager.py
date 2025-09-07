"""電源管理サービス。"""

from __future__ import annotations

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import PowerPort
from splat_replay.shared.config import BehaviorSettings


class PowerManager:
    """PC の電源操作を担当するサービス。"""

    def __init__(
        self,
        power: PowerPort,
        settings: BehaviorSettings,
        logger: BoundLogger,
    ) -> None:
        self.power = power
        self.logger = logger
        self.settings = settings

    async def sleep(self) -> None:
        if not self.settings.sleep_after_upload:
            self.logger.info("PC スリープは無効化されています")
            return

        self.logger.info("PC スリープ")
        await self.power.sleep()
