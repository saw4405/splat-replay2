"""ブキ判別の固定値。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from splat_replay.infrastructure.filesystem.paths import RUNTIME_ROOT

ALLY_SLOTS: Final[tuple[str, ...]] = ("ally_1", "ally_2", "ally_3", "ally_4")
ENEMY_SLOTS: Final[tuple[str, ...]] = (
    "enemy_1",
    "enemy_2",
    "enemy_3",
    "enemy_4",
)
SLOT_ORDER: Final[tuple[str, ...]] = ALLY_SLOTS + ENEMY_SLOTS

SLOT_BOXES: Final[dict[str, tuple[int, int, int, int]]] = {
    "ally_1": (520, 20, 610, 120),
    "ally_2": (610, 20, 700, 120),
    "ally_3": (700, 20, 790, 120),
    "ally_4": (790, 20, 880, 120),
    "enemy_1": (1040, 20, 1130, 120),
    "enemy_2": (1130, 20, 1220, 120),
    "enemy_3": (1220, 20, 1310, 120),
    "enemy_4": (1310, 20, 1400, 120),
}

UNKNOWN_WEAPON_LABEL: Final[str] = "不明"
QUERY_MATCH_MAX_SHIFT_PX: Final[int] = 8

TEAM_COLOR_SAMPLE_POINT: Final[tuple[int, int]] = (45, 8)
TEAM_COLOR_WITHIN_MAX_DISTANCE: Final[float] = 90.0
TEAM_COLOR_BETWEEN_MIN_DISTANCE: Final[float] = 110.0
SCORE_TIE_EPSILON: Final[float] = 1e-12

OUTLINE_MODEL_VOTE_RATIO: Final[float] = 0.35
OUTLINE_MODEL_MAX_SHIFT: Final[int] = 20
OUTLINE_ALIGN_MAX_SHIFT: Final[int] = 24

OUTLINE_MODEL_MASK_FILES: Final[dict[str, str]] = {
    "ika": "outline/models/outline_model_ika_mask.png",
    "tako": "outline/models/outline_model_tako_mask.png",
}
OUTLINE_INPUT_PREFIX: Final[dict[str, str]] = {
    "ika": "outline/inputs/outline_input_ika_",
    "tako": "outline/inputs/outline_input_tako_",
}

WEAPON_TEMPLATE_MATCHER_GROUP: Final[str] = "weapon_templates"

UNMATCHED_OUTPUT_DIR: Final[Path] = (
    RUNTIME_ROOT / "outputs" / "predict_weapons" / "unmatched"
)
INVALID_FILENAME_CHARS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r'[\\/:*?"<>|]'
)
