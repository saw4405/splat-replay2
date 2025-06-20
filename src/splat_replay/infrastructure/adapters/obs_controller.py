"""OBS 操作アダプタ。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import OBSControlPort
from splat_replay.shared.logger import get_logger

logger = get_logger()


class OBSController(OBSControlPort):
    """OBS Studio と連携する。"""

    def start(self) -> None:
        """録画開始指示を送る。"""
        logger.info("OBS 録画開始指示")
        raise NotImplementedError

    def stop(self) -> Path:
        """録画停止指示を送る。"""
        logger.info("OBS 録画停止指示")
        raise NotImplementedError

    def pause(self) -> None:
        """録画を一時停止する。"""
        logger.info("OBS 録画一時停止指示")
        raise NotImplementedError

    def resume(self) -> None:
        """録画を再開する。"""
        logger.info("OBS 録画再開指示")
        raise NotImplementedError

    def is_running(self) -> bool:
        """OBS が起動しているか確認する。"""
        logger.info("OBS 起動状態確認")
        raise NotImplementedError

    def launch(self) -> None:
        """OBS を起動する。"""
        logger.info("OBS 起動指示")
        raise NotImplementedError

    def start_virtual_camera(self) -> None:
        """OBS の仮想カメラを開始する。"""
        logger.info("OBS 仮想カメラ開始指示")
        raise NotImplementedError
