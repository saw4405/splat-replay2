"""録画一覧表示テーブル。"""

from __future__ import annotations


class RecordingTable:
    """収録済みデータを一覧するプレースホルダー。"""

    def refresh(self) -> None:
        """表示を更新する。"""
        raise NotImplementedError
