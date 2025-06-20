"""OBS 操作アダプタ。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import OBSControlPort


class OBSController(OBSControlPort):
    """OBS Studio と連携する。"""

    def start(self) -> None:
        """録画開始指示を送る。"""
        raise NotImplementedError

    def stop(self) -> Path:
        """録画停止指示を送る。"""
        raise NotImplementedError

    def pause(self) -> None:
        """録画を一時停止する。"""
        raise NotImplementedError

    def resume(self) -> None:
        """録画を再開する。"""
        raise NotImplementedError

    def is_running(self) -> bool:
        """OBS が起動しているか確認する。"""
        raise NotImplementedError

    def launch(self) -> None:
        """OBS を起動する。"""
        raise NotImplementedError

    def start_virtual_camera(self) -> None:
        """OBS の仮想カメラを開始する。"""
        raise NotImplementedError
