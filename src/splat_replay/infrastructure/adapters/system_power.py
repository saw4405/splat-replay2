"""電源制御アダプタ。"""

from __future__ import annotations

import os

from splat_replay.shared.logger import get_logger

logger = get_logger()


class SystemPower:
    """OS の電源制御を提供する。"""

    def sleep(self) -> None:
        """PC をスリープさせる。"""
        logger.info("PC スリープ指示")
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
