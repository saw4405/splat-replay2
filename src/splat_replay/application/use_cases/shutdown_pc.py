"""PC スリープユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import PowerPort


class ShutdownPCUseCase:
    """電源操作を行う。"""

    def __init__(self, power: PowerPort) -> None:
        self.power = power

    def execute(self) -> None:
        """PC をスリープさせる。"""
        self.power.sleep()
