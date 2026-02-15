"""ブキ判別用クエリ画像生成。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from . import constants, outline_models
from .team_color import detect_slot_team_region


@dataclass(frozen=True)
class QuerySlotData:
    """1スロット分の照合用データ。"""

    rgba: np.ndarray
    gray: np.ndarray
    padded_gray: np.ndarray
    weapon_only_rgba: np.ndarray
    weapon_only_mask: np.ndarray


def crop_slot_images(frame: np.ndarray) -> dict[str, np.ndarray]:
    """1920x1080フレームから8スロットを切り出す。"""
    slots: dict[str, np.ndarray] = {}
    for slot, (x1, y1, x2, y2) in constants.SLOT_BOXES.items():
        slots[slot] = frame[y1:y2, x1:x2].copy()
    return slots


def build_query_slot_data(
    *,
    slot_images: dict[str, np.ndarray],
    model_masks: dict[str, np.ndarray],
) -> dict[str, QuerySlotData]:
    """スロット画像群から判別用クエリを生成する。"""
    result: dict[str, QuerySlotData] = {}
    for slot in constants.SLOT_ORDER:
        slot_bgr = slot_images[slot]
        rgba = cv2.cvtColor(slot_bgr, cv2.COLOR_BGR2RGBA)
        gray = cv2.cvtColor(slot_bgr, cv2.COLOR_BGR2GRAY)

        team_region_mask = detect_slot_team_region(slot_bgr)
        if int(team_region_mask.sum()) > 0:
            _, aligned_model_mask = outline_models.infer_species_and_mask(
                detected_mask=team_region_mask,
                model_masks=model_masks,
            )
            base_alpha = (aligned_model_mask > 0).astype(np.uint8)
        else:
            base_alpha = np.zeros_like(gray, dtype=np.uint8)

        weapon_alpha = np.where(
            (base_alpha > 0) & (team_region_mask == 0), 255, 0
        ).astype(np.uint8)
        weapon_only_rgba = np.dstack([rgba[:, :, :3], weapon_alpha])

        padded_gray = cv2.copyMakeBorder(
            gray,
            constants.QUERY_MATCH_MAX_SHIFT_PX,
            constants.QUERY_MATCH_MAX_SHIFT_PX,
            constants.QUERY_MATCH_MAX_SHIFT_PX,
            constants.QUERY_MATCH_MAX_SHIFT_PX,
            borderType=cv2.BORDER_REPLICATE,
        )

        result[slot] = QuerySlotData(
            rgba=rgba,
            gray=gray,
            padded_gray=padded_gray,
            weapon_only_rgba=weapon_only_rgba,
            weapon_only_mask=weapon_alpha,
        )
    return result
