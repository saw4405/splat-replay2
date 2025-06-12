"""バトルルールの列挙型。"""

from __future__ import annotations

from enum import Enum


class Rule(Enum):
    """スプラトゥーンの主要ルール。"""

    TURF_WAR = "turf_war"
    SPLAT_ZONES = "splat_zones"
    TOWER_CONTROL = "tower_control"
    RAINMAKER = "rainmaker"
    CLAM_BLITZ = "clam_blitz"
