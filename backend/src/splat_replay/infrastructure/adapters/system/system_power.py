"""電源制御アダプタ。"""

from __future__ import annotations

import asyncio

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import PowerPort


class SystemPower(PowerPort):
    """OS の電源制御を提供する。"""

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger

    async def sleep(self) -> None:
        """PC をスリープさせる。"""
        self.logger.info("PC スリープ指示")
        process = await asyncio.create_subprocess_exec(
            "rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"
        )
        await process.wait()
