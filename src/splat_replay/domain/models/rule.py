"""バトルルールの列挙型。"""

from __future__ import annotations

from enum import Enum


class Rule(Enum):
    """スプラトゥーンの主要ルール。"""

    TURF_WAR = "ナワバリバトル"
    RAINMAKER = "ガチホコ"
    SPLAT_ZONES = "ガチエリア"
    TOWER_CONTROL = "ガチヤグラ"
    CLAM_BLITZ = "ガチアサリ"
    TRICOLOR_TURF_WAR = "トリカラバトル"
