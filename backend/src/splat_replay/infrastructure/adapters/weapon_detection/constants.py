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
WEAPON_DISPLAY_OUTLINE_MIN_IOU: Final[float] = 0.40
WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS: Final[int] = 4
# 輪郭一致スロットで推定した「ブキ本体領域」の平均比率が低すぎる場合は
# ブキ表示が薄い/欠落しているとみなし、表示あり判定を抑制する。
WEAPON_DISPLAY_MIN_WEAPON_REGION_RATIO: Final[float] = 0.08
# 輪郭一致スロットのチームカラー領域内エッジ密度が高すぎる場合は、
# チームカラーが塗り切れていない段階の偽陽性とみなし、表示あり判定を抑制する。
WEAPON_DISPLAY_MAX_MATCHED_SLOT_TEAM_EDGE_RATIO: Final[float] = 0.15
# 輪郭一致スロットのブキ本体領域が低コントラストすぎる場合は、
# ブキ表示が薄い/欠落しているとみなし、表示あり判定を抑制する。
WEAPON_DISPLAY_MIN_MATCHED_SLOT_WEAPON_REGION_GRAY_STD: Final[float] = 40.0
SCORE_TIE_EPSILON: Final[float] = 1e-12

# 候補の最終選択は score と template_threshold の単一スコアで一貫して行う。
# confidence = score - (weight * threshold)
# confidence が accept_threshold 未満なら UNKNOWN とする。
CANDIDATE_CONFIDENCE_THRESHOLD_WEIGHT: Final[float] = 1.31
CANDIDATE_CONFIDENCE_ACCEPT_THRESHOLD: Final[float] = -0.29
# UNKNOWN 判定のうち、証拠量が十分なケースのみを追加受理する救済パラメータ。
# rescue_threshold = accept_threshold - rescue_margin
CANDIDATE_CONFIDENCE_RESCUE_MARGIN: Final[float] = 0.24
CANDIDATE_CONFIDENCE_RESCUE_MIN_GAP: Final[float] = 0.0085
CANDIDATE_CONFIDENCE_RESCUE_MIN_EDGE_RATIO: Final[float] = 0.09
CANDIDATE_CONFIDENCE_RESCUE_MIN_TEAM_EDGE_RATIO: Final[float] = 0.07
CANDIDATE_CONFIDENCE_RESCUE_MAX_THRESHOLD: Final[float] = 0.95
# 一部の近縁ブキは top2 が特定ペアかつ score 差が小さい場合だけ、
# variant を含めたペア限定再判定を行う。
PAIR_VARIANT_RERANK_RULES: Final[tuple[tuple[tuple[str, str], float], ...]] = (
    (("4Kスコープ", "リッター4K"), 0.03),
    (("スプラスコープ", "スプラチャージャー"), 0.07),
    (("ジェットスイーパーカスタム", "デュアルスイーパーカスタム"), 0.06),
)
# pair rerank 後も confidence では逆転しない family だけ、
# variant 追加で大きく改善した側を限定的に rescue する。
PAIR_VARIANT_RESCUE_RULES: Final[
    tuple[tuple[tuple[str, str], str, float], ...]
] = ((("スプラスコープ", "スプラチャージャー"), "スプラスコープ", 0.05),)
# 一部の残件は top1 が特定ブキかつ raw score が低いケースに偏るため、
# そのときだけ family 候補を variant 込みで限定再判定する。
TOP1_VARIANT_RERANK_RULES: Final[
    tuple[tuple[str, tuple[str, ...], float], ...]
] = (
    (
        "パブロ",
        ("パブロ", "パブロ・ヒュー", "N-ZAP89", "Rブラスターエリートデコ"),
        0.86,
    ),
    (
        "カーボンローラー",
        ("カーボンローラー", "カーボンローラーデコ"),
        0.86,
    ),
    (
        "ダイナモローラー",
        ("ダイナモローラー", "ダイナモローラーテスラ"),
        0.84,
    ),
    (
        "トライストリンガー",
        ("トライストリンガー", "トライストリンガーコラボ"),
        0.80,
    ),
)
# variant テンプレートは、通常判定が拮抗した場合のみ再判定に使用する。
VARIANT_FALLBACK_MAX_CONFIDENCE_GAP: Final[float] = 0.02
# ブキ表示が実質見えていない低信号スロットは強制的に UNKNOWN とする。
LOW_SIGNAL_EDGE_RATIO_MAX: Final[float] = 0.001
LOW_SIGNAL_TEAM_EDGE_RATIO_MAX: Final[float] = 0.001

# テンプレートマッチ応答の集約点数。1 は従来どおり最大値のみを使う。
TEMPLATE_RESPONSE_TOP_K: Final[int] = 1

OUTLINE_MODEL_VOTE_RATIO: Final[float] = 0.35
OUTLINE_MODEL_MAX_SHIFT: Final[int] = 20
OUTLINE_ALIGN_FAST_MAX_SHIFT: Final[int] = 8
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
LABELING_VARIANT_MANIFEST_RELATIVE_PATH: Final[Path] = Path(
    "matching/weapon/generated_labeling_variants/manifest.json"
)
LABELING_VARIANT_RERANK_TOP_WEAPONS: Final[int] = 5

UNMATCHED_OUTPUT_DIR: Final[Path] = (
    RUNTIME_ROOT / "outputs" / "predict_weapons" / "unmatched"
)
INVALID_FILENAME_CHARS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r'[\\/:*?"<>|]'
)
