"""電源管理サービス。"""

from __future__ import annotations

from splat_replay.application.interfaces import (
    ConfigPort,
    LoggerPort,
    PowerPort,
)


class PowerManager:
    """PC の電源操作を担当するサービス。"""

    def __init__(
        self,
        power: PowerPort,
        config: ConfigPort,
        logger: LoggerPort,
    ) -> None:
        self.power = power
        self.logger = logger
        self.config = config

    async def sleep(self) -> None:
        settings = self.config.get_behavior_settings()
        if not settings.sleep_after_upload:
            self.logger.info("PC スリープは無効化されています")
            return

        self.logger.info("PC スリープ")
        await self.power.sleep()
