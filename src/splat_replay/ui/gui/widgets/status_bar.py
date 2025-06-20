"""録画状態バーウィジェット。"""

from __future__ import annotations


class RecordingStatusBar:
    """録画状態を表示するプレースホルダー。"""

    def set_recording(self) -> None:
        """録画開始状態に更新する。"""
        raise NotImplementedError
