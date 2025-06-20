"""PC スリープユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import PowerPort
from splat_replay.shared.logger import get_logger


class ShutdownPCUseCase:
    """電源操作を行う。"""

    def __init__(self, power: PowerPort) -> None:
        self.power = power
        self.logger = get_logger()

    def execute(self) -> None:
        """PC をスリープさせる。"""
        self.logger.info("PC スリープ")
        self.power.sleep()
