"""電源制御アダプタ。"""

from __future__ import annotations

import os

from structlog.stdlib import BoundLogger


class SystemPower:
    """OS の電源制御を提供する。"""

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger

    def sleep(self) -> None:
        """PC をスリープさせる。"""
        self.logger.info("PC スリープ指示")
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
