"""Desktop notification port."""

from __future__ import annotations

from typing import Protocol


class DesktopNotificationPort(Protocol):
    """デスクトップ OS の通知センターへ通知を登録する。"""

    async def send(self, title: str, body: str) -> None:
        """通知を登録する。拒否または登録失敗時は例外を送出する。"""
        ...
