"""OBS 操作アダプタ。"""

from __future__ import annotations

from pathlib import Path


class OBSController:
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
