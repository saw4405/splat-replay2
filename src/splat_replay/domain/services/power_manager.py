"""電源管理サービス。"""

from __future__ import annotations

from splat_replay.shared.logger import get_logger

logger = get_logger()


class PowerManager:
    """システムの電源制御を担当する。"""

    def sleep(self) -> None:
        """PC をスリープ状態にする。"""
        logger.info("PC スリープ実行")
        raise NotImplementedError
