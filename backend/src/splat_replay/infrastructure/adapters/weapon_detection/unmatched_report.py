"""未一致スロットの検証出力。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from splat_replay.application.interfaces import (
    WeaponCandidateScore,
    WeaponSlotResult,
)

from . import constants
from .query_builder import QuerySlotData


def save_unmatched_slots(
    *,
    frame: np.ndarray,
    query_data_by_slot: dict[str, QuerySlotData],
    slot_results: dict[str, WeaponSlotResult],
    candidate_thresholds_by_slot: dict[str, dict[str, float]],
    trace_id: str | None = None,
) -> str:
    """未一致時の追跡情報を保存し、出力ディレクトリを返す。"""
    output_dir = _prepare_unmatched_output_dir(trace_id=trace_id)

    input_frame_path = output_dir / "input_frame.png"
    cv2.imwrite(str(input_frame_path), frame)

    rows: list[dict[str, object]] = []
    unmatched_count = 0
    for slot in constants.SLOT_ORDER:
        slot_result = slot_results[slot]
        query_data = query_data_by_slot[slot]
        threshold_by_weapon = candidate_thresholds_by_slot.get(slot, {})
        top_candidates = slot_result.top_candidates
        top1 = top_candidates[0] if len(top_candidates) >= 1 else None
        top2 = top_candidates[1] if len(top_candidates) >= 2 else None
        top3 = top_candidates[2] if len(top_candidates) >= 3 else None

        weapon_only_path: Path | None = None
        mask_path: Path | None = None
        if slot_result.is_unmatched:
            unmatched_count += 1
            weapon_only_path = output_dir / f"{slot}_weapon_only.png"
            mask_path = output_dir / f"{slot}_mask.png"
            Image.fromarray(query_data.weapon_only_rgba, mode="RGBA").save(
                weapon_only_path
            )
            Image.fromarray(query_data.weapon_only_mask, mode="L").save(
                mask_path
            )

        rows.append(
            {
                "slot": slot,
                "predicted_weapon": slot_result.predicted_weapon,
                "is_unmatched": slot_result.is_unmatched,
                "threshold": _resolve_threshold(
                    slot_result=slot_result,
                    top1=top1,
                    threshold_by_weapon=threshold_by_weapon,
                ),
                "top1": _to_candidate_row(top1, threshold_by_weapon),
                "top2": _to_candidate_row(top2, threshold_by_weapon),
                "top3": _to_candidate_row(top3, threshold_by_weapon),
                "saved_weapon_only": (
                    _as_path_string(weapon_only_path)
                    if weapon_only_path is not None
                    else None
                ),
                "saved_mask": (
                    _as_path_string(mask_path)
                    if mask_path is not None
                    else None
                ),
            }
        )

    summary_json = {
        "input_image": _as_path_string(input_frame_path),
        "unmatched_count": unmatched_count,
        "rows": rows,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return _as_path_string(output_dir)


def _prepare_unmatched_output_dir(*, trace_id: str | None) -> Path:
    trace = _sanitize_trace_id(trace_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = constants.UNMATCHED_OUTPUT_DIR / f"{trace}_{timestamp}"
    suffix = 2
    while output_dir.exists():
        output_dir = (
            constants.UNMATCHED_OUTPUT_DIR / f"{trace}_{timestamp}_{suffix}"
        )
        suffix += 1
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def _sanitize_trace_id(trace_id: str | None) -> str:
    base = (trace_id or "frame").strip() or "frame"
    sanitized = constants.INVALID_FILENAME_CHARS_PATTERN.sub("_", base)
    return sanitized


def _to_candidate_row(
    candidate: WeaponCandidateScore | None,
    threshold_by_weapon: dict[str, float],
) -> dict[str, object] | None:
    if candidate is None:
        return None
    return {
        "weapon": candidate.weapon,
        "score": candidate.score,
        "threshold": threshold_by_weapon.get(candidate.weapon),
    }


def _resolve_threshold(
    *,
    slot_result: WeaponSlotResult,
    top1: WeaponCandidateScore | None,
    threshold_by_weapon: dict[str, float],
) -> float | None:
    if not slot_result.is_unmatched:
        return threshold_by_weapon.get(slot_result.predicted_weapon)
    if top1 is None:
        return None
    return threshold_by_weapon.get(top1.weapon)


def _as_path_string(path: Path) -> str:
    return path.resolve().as_posix()
