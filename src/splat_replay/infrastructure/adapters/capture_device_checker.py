"""キャプチャデバイス接続確認アダプタ。"""

from __future__ import annotations

from splat_replay.application.interfaces import CaptureDevicePort
from splat_replay.shared.logger import get_logger

logger = get_logger()


class CaptureDeviceChecker(CaptureDevicePort):
    """キャプチャデバイスの接続状態を確認する。"""

    def is_connected(self) -> bool:
        """デバイスが接続済みかを返す。"""
        logger.info("キャプチャデバイス接続確認")
        raise NotImplementedError
