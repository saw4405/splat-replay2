"""録画制御サービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.shared.logger import get_logger

logger = get_logger()


class Recorder:
    """OBS を操作して録画を管理する。"""

    def start(self) -> None:
        """録画を開始する。"""
        logger.info("録画開始指示")
        raise NotImplementedError

    def stop(self) -> Path:
        """録画を停止し、ファイルパスを返す。"""
        logger.info("録画停止指示")
        raise NotImplementedError

    def pause(self) -> None:
        """録画を一時停止する。"""
        logger.info("録画一時停止指示")
        raise NotImplementedError

    def resume(self) -> None:
        """録画を再開する。"""
        logger.info("録画再開指示")
        raise NotImplementedError
