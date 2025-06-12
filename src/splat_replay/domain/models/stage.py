"""ステージの列挙型（代表的な数種類のみ）。"""

from __future__ import annotations

from enum import Enum


class Stage(Enum):
    """ゲーム内ステージ。"""

    SCORCH_GORGE = "scorch_gorge"
    EELTAIL_ALLEY = "eeltail_alley"
    HAGGLEFISH_MARKET = "hagglefish_market"
