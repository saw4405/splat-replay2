"""電源管理サービス。"""

from __future__ import annotations


class PowerManager:
    """システムの電源制御を担当する。"""

    def sleep(self) -> None:
        """PC をスリープ状態にする。"""
        raise NotImplementedError
