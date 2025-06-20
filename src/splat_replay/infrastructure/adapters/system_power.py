"""電源制御アダプタ。"""

from __future__ import annotations


class SystemPower:
    """OS の電源制御を提供する。"""

    def sleep(self) -> None:
        """PC をスリープさせる。"""
        raise NotImplementedError
