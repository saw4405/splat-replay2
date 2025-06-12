"""バトル結果を表す列挙型。"""

from __future__ import annotations

from enum import Enum


class Result(Enum):
    """勝敗。"""

    WIN = "win"
    LOSE = "lose"
