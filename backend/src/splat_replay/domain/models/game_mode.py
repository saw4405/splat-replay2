"""ゲームモード定義。"""

from __future__ import annotations

from enum import Enum


class GameMode(Enum):
    """ゲームモードを表す列挙型。"""

    BATTLE = "バトルモード"
    SALMON = "バイトモード"
