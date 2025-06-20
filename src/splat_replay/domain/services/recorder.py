"""録画制御サービス。"""

from __future__ import annotations

from pathlib import Path


class Recorder:
    """OBS を操作して録画を管理する。"""

    def start(self) -> None:
        """録画を開始する。"""
        raise NotImplementedError

    def stop(self) -> Path:
        """録画を停止し、ファイルパスを返す。"""
        raise NotImplementedError

    def pause(self) -> None:
        """録画を一時停止する。"""
        raise NotImplementedError

    def resume(self) -> None:
        """録画を再開する。"""
        raise NotImplementedError
