"""ゲームモード定義。"""

from __future__ import annotations

from enum import Enum, auto


class GameMode(Enum):
    """ゲームモードを表す列挙型。"""

    UNKNOWN = auto()
    BATTLE = auto()
    SALMON = auto()
