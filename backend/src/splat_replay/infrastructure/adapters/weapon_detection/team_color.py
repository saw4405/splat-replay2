"""チームカラー関連処理。"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from . import constants

MORPH_KERNEL = np.ones((3, 3), dtype=np.uint8)

CREAM_MAX_SATURATION = 80
STRICT_HUE_TOLERANCE_DEGREE = 14
RELAXED_HUE_TOLERANCE_DEGREE = 22
STRICT_CREAM_SATURATION_TOLERANCE = 35
RELAXED_CREAM_SATURATION_TOLERANCE = 55
STRICT_COLOR_SATURATION_TOLERANCE = 65
RELAXED_COLOR_SATURATION_TOLERANCE = 90
STRICT_CREAM_VALUE_DROP = 70
RELAXED_CREAM_VALUE_DROP = 110
STRICT_COLOR_VALUE_DROP = 80
RELAXED_COLOR_VALUE_DROP = 120
STRICT_CREAM_MIN_VALUE = 90
RELAXED_CREAM_MIN_VALUE = 80
STRICT_COLOR_MIN_VALUE = 120
RELAXED_COLOR_MIN_VALUE = 90
MIN_COMPONENT_AREA = 20
SPLIT_MERGE_MIN_OVERLAP_RATIO = 0.35
SPLIT_MERGE_MAX_VERTICAL_GAP = 30
SPLIT_MERGE_MAX_HORIZONTAL_GAP = 6
SPLIT_MERGE_MAX_ABOVE_ANCHOR = 5


@dataclass(frozen=True)
class TeamColorScreenMetrics:
    """ブキ表示画面判定に使う距離指標。"""

    allies_max_distance: float
    enemies_max_distance: float
    teams_min_distance: float


def sample_slot_rgb(slot_image: np.ndarray) -> tuple[int, int, int]:
    """スロット画像のサンプル点RGBを返す。"""
    x, y = constants.TEAM_COLOR_SAMPLE_POINT
    bgr = slot_image[y, x]
    return int(bgr[2]), int(bgr[1]), int(bgr[0])


def detect_weapon_display_screen(
    slot_images: dict[str, np.ndarray],
) -> tuple[bool, TeamColorScreenMetrics]:
    """味方4同色/敵4同色/味方敵異色の条件を判定する。"""
    ally_colors = [
        sample_slot_rgb(slot_images[slot]) for slot in constants.ALLY_SLOTS
    ]
    enemy_colors = [
        sample_slot_rgb(slot_images[slot]) for slot in constants.ENEMY_SLOTS
    ]

    metrics = TeamColorScreenMetrics(
        allies_max_distance=_max_pairwise_rgb_distance(ally_colors),
        enemies_max_distance=_max_pairwise_rgb_distance(enemy_colors),
        teams_min_distance=_min_pairwise_rgb_distance(
            ally_colors, enemy_colors
        ),
    )

    is_display = (
        metrics.allies_max_distance <= constants.TEAM_COLOR_WITHIN_MAX_DISTANCE
        and metrics.enemies_max_distance
        <= constants.TEAM_COLOR_WITHIN_MAX_DISTANCE
        and metrics.teams_min_distance
        >= constants.TEAM_COLOR_BETWEEN_MIN_DISTANCE
    )
    return is_display, metrics


def detect_slot_team_region(slot_bgr: np.ndarray) -> np.ndarray:
    """スロット内のイカ/タコ帯（チームカラー領域）を抽出する。"""
    strict_mask = _build_color_mask(slot_bgr, strict=True)
    relaxed_mask = _build_color_mask(slot_bgr, strict=False)

    if strict_mask.sum() == 0 and relaxed_mask.sum() == 0:
        return np.zeros(slot_bgr.shape[:2], dtype=np.uint8)

    strict_anchor = _pick_component_near_sample(strict_mask)
    if strict_anchor.sum() == 0:
        strict_anchor = _pick_component_near_sample(relaxed_mask)

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        relaxed_mask, connectivity=8
    )
    if component_count <= 1:
        return (relaxed_mask > 0).astype(np.uint8)

    anchor_ids = [
        int(component_id)
        for component_id in np.unique(labels[strict_anchor > 0])
        if component_id > 0
    ]
    if not anchor_ids:
        return strict_anchor

    anchor_component_id = max(
        anchor_ids,
        key=lambda component_id: int(stats[component_id, cv2.CC_STAT_AREA]),
    )
    merged = _merge_split_components(
        labels,
        stats,
        anchor_component_id=anchor_component_id,
    )
    merged = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, MORPH_KERNEL)
    return (merged > 0).astype(np.uint8)


def _rgb_distance(
    rgb_a: tuple[int, int, int], rgb_b: tuple[int, int, int]
) -> float:
    return math.sqrt(
        (rgb_a[0] - rgb_b[0]) ** 2
        + (rgb_a[1] - rgb_b[1]) ** 2
        + (rgb_a[2] - rgb_b[2]) ** 2
    )


def _max_pairwise_rgb_distance(colors: list[tuple[int, int, int]]) -> float:
    max_distance = 0.0
    for index, color_a in enumerate(colors):
        for color_b in colors[index + 1 :]:
            max_distance = max(max_distance, _rgb_distance(color_a, color_b))
    return max_distance


def _min_pairwise_rgb_distance(
    colors_a: list[tuple[int, int, int]],
    colors_b: list[tuple[int, int, int]],
) -> float:
    min_distance = float("inf")
    for color_a in colors_a:
        for color_b in colors_b:
            min_distance = min(min_distance, _rgb_distance(color_a, color_b))
    return min_distance


def _hue_distance_degree(
    hue_degree: np.ndarray, base_degree: int
) -> np.ndarray:
    diff = np.abs(hue_degree - base_degree)
    return np.minimum(diff, 360 - diff)


def _build_color_mask(slot_bgr: np.ndarray, *, strict: bool) -> np.ndarray:
    hsv = cv2.cvtColor(slot_bgr, cv2.COLOR_BGR2HSV)
    sample_x, sample_y = constants.TEAM_COLOR_SAMPLE_POINT
    sample_h, sample_s, sample_v = [int(v) for v in hsv[sample_y, sample_x]]
    sample_hue_degree = sample_h * 2
    is_cream = sample_s <= CREAM_MAX_SATURATION

    hue_degree = hsv[:, :, 0].astype(np.int32) * 2
    saturation = hsv[:, :, 1].astype(np.int32)
    value = hsv[:, :, 2].astype(np.int32)

    hue_tolerance = (
        STRICT_HUE_TOLERANCE_DEGREE if strict else RELAXED_HUE_TOLERANCE_DEGREE
    )
    if is_cream:
        saturation_tolerance = (
            STRICT_CREAM_SATURATION_TOLERANCE
            if strict
            else RELAXED_CREAM_SATURATION_TOLERANCE
        )
        min_value = max(
            STRICT_CREAM_MIN_VALUE if strict else RELAXED_CREAM_MIN_VALUE,
            sample_v
            - (
                STRICT_CREAM_VALUE_DROP if strict else RELAXED_CREAM_VALUE_DROP
            ),
        )
    else:
        saturation_tolerance = (
            STRICT_COLOR_SATURATION_TOLERANCE
            if strict
            else RELAXED_COLOR_SATURATION_TOLERANCE
        )
        min_value = max(
            STRICT_COLOR_MIN_VALUE if strict else RELAXED_COLOR_MIN_VALUE,
            sample_v
            - (
                STRICT_COLOR_VALUE_DROP if strict else RELAXED_COLOR_VALUE_DROP
            ),
        )

    hue_match = (
        _hue_distance_degree(hue_degree, sample_hue_degree) <= hue_tolerance
    )
    saturation_match = np.abs(saturation - sample_s) <= saturation_tolerance
    value_match = value >= min_value
    raw_mask = (hue_match & saturation_match & value_match).astype(np.uint8)

    binary = raw_mask * 255
    binary = cv2.medianBlur(binary, 3)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, MORPH_KERNEL)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, MORPH_KERNEL)
    return (binary > 0).astype(np.uint8)


def _pick_component_near_sample(mask: np.ndarray) -> np.ndarray:
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )
    if component_count <= 1:
        return np.zeros_like(mask, dtype=np.uint8)

    sample_x, sample_y = constants.TEAM_COLOR_SAMPLE_POINT
    sample_component_id = int(labels[sample_y, sample_x])
    if (
        sample_component_id > 0
        and stats[sample_component_id, cv2.CC_STAT_AREA] >= MIN_COMPONENT_AREA
    ):
        return (labels == sample_component_id).astype(np.uint8)

    nearest_component_id = 0
    nearest_distance: float | None = None
    for component_id in range(1, component_count):
        area = int(stats[component_id, cv2.CC_STAT_AREA])
        if area < MIN_COMPONENT_AREA:
            continue
        x = int(stats[component_id, cv2.CC_STAT_LEFT])
        y = int(stats[component_id, cv2.CC_STAT_TOP])
        width = int(stats[component_id, cv2.CC_STAT_WIDTH])
        height = int(stats[component_id, cv2.CC_STAT_HEIGHT])
        center_x = x + width / 2.0
        center_y = y + height / 2.0
        distance = (center_x - sample_x) ** 2 + (center_y - sample_y) ** 2
        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_component_id = component_id

    if nearest_component_id == 0:
        return np.zeros_like(mask, dtype=np.uint8)
    return (labels == nearest_component_id).astype(np.uint8)


def _merge_split_components(
    labels: np.ndarray,
    stats: np.ndarray,
    *,
    anchor_component_id: int,
) -> np.ndarray:
    anchor_y = int(stats[anchor_component_id, cv2.CC_STAT_TOP])
    selected_component_ids = {anchor_component_id}

    has_change = True
    while has_change:
        has_change = False
        for component_id in range(1, stats.shape[0]):
            if component_id in selected_component_ids:
                continue

            area = int(stats[component_id, cv2.CC_STAT_AREA])
            if area < MIN_COMPONENT_AREA:
                continue

            x = int(stats[component_id, cv2.CC_STAT_LEFT])
            y = int(stats[component_id, cv2.CC_STAT_TOP])
            width = int(stats[component_id, cv2.CC_STAT_WIDTH])
            height = int(stats[component_id, cv2.CC_STAT_HEIGHT])
            x2 = x + width - 1
            y2 = y + height - 1
            if y2 < anchor_y - SPLIT_MERGE_MAX_ABOVE_ANCHOR:
                continue

            should_select = False
            for selected_id in tuple(selected_component_ids):
                selected_x = int(stats[selected_id, cv2.CC_STAT_LEFT])
                selected_y = int(stats[selected_id, cv2.CC_STAT_TOP])
                selected_w = int(stats[selected_id, cv2.CC_STAT_WIDTH])
                selected_h = int(stats[selected_id, cv2.CC_STAT_HEIGHT])
                selected_x2 = selected_x + selected_w - 1
                selected_y2 = selected_y + selected_h - 1

                overlap_x = max(
                    0, min(selected_x2, x2) - max(selected_x, x) + 1
                )
                overlap_y = max(
                    0, min(selected_y2, y2) - max(selected_y, y) + 1
                )
                overlap_x_ratio = overlap_x / float(min(selected_w, width))
                overlap_y_ratio = overlap_y / float(min(selected_h, height))

                if y > selected_y2:
                    vertical_gap = y - selected_y2 - 1
                elif selected_y > y2:
                    vertical_gap = selected_y - y2 - 1
                else:
                    vertical_gap = 0

                if x > selected_x2:
                    horizontal_gap = x - selected_x2 - 1
                elif selected_x > x2:
                    horizontal_gap = selected_x - x2 - 1
                else:
                    horizontal_gap = 0

                vertical_split_connected = (
                    overlap_x_ratio >= SPLIT_MERGE_MIN_OVERLAP_RATIO
                    and vertical_gap <= SPLIT_MERGE_MAX_VERTICAL_GAP
                )
                horizontal_split_connected = (
                    overlap_y_ratio >= SPLIT_MERGE_MIN_OVERLAP_RATIO
                    and horizontal_gap <= SPLIT_MERGE_MAX_HORIZONTAL_GAP
                )
                if vertical_split_connected or horizontal_split_connected:
                    should_select = True
                    break

            if should_select:
                selected_component_ids.add(component_id)
                has_change = True

    return np.isin(labels, list(selected_component_ids)).astype(np.uint8)
