"""ゲーム映像プレビュー用ウィジェット。"""

from __future__ import annotations


class GamePreviewWidget:
    """映像を表示するプレースホルダー。"""

    def update_frame(self) -> None:
        """フレームを更新する。"""
        raise NotImplementedError
