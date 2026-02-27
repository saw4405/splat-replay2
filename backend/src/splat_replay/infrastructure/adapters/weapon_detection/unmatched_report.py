"""ブキ判別結果の検証出力。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from splat_replay.application.interfaces import WeaponSlotResult

from . import constants
from .query_builder import QuerySlotData


@dataclass(frozen=True)
class SlotDebugCandidate:
    """レポート出力用の候補情報。"""

    weapon: str
    score: float
    threshold: float


def save_unmatched_slots(
    *,
    frame: np.ndarray,
    query_data_by_slot: dict[str, QuerySlotData],
    slot_results: dict[str, WeaponSlotResult],
    slot_debug_candidates_by_slot: dict[str, tuple[SlotDebugCandidate, ...]],
    trace_id: str | None = None,
    target_slots: set[str] | None = None,
) -> str:
    """追跡情報を保存し、出力ディレクトリを返す。"""
    output_dir = _prepare_unmatched_output_dir(trace_id=trace_id)

    input_frame_path = output_dir / "input_frame.png"
    cv2.imwrite(str(input_frame_path), frame)

    # レポート出力時は常に全8スロット分を出力
    report_slots = constants.SLOT_ORDER
    rows: list[dict[str, object]] = []
    unmatched_count = 0
    for slot in report_slots:
        slot_result = slot_results[slot]
        query_data = query_data_by_slot[slot]
        candidates = slot_debug_candidates_by_slot.get(slot, ())
        top1 = candidates[0] if len(candidates) >= 1 else None

        top1_weapon_for_file = _resolve_top1_weapon_for_file_name(
            slot_result=slot_result,
            top1=top1,
        )
        top1_score_for_file = _resolve_top1_score_for_file_name(top1=top1)
        predicted_score = _resolve_predicted_score(
            slot_result=slot_result,
            candidates=candidates,
        )
        file_tag = _build_slot_file_tag(
            slot=slot,
            top1_weapon=top1_weapon_for_file,
            top1_score=top1_score_for_file,
        )

        slot_image_path = output_dir / f"{file_tag}_slot.png"
        weapon_only_path = output_dir / f"{file_tag}_weapon_only.png"
        mask_path = output_dir / f"{file_tag}_mask.png"
        Image.fromarray(query_data.rgba, mode="RGBA").save(slot_image_path)
        Image.fromarray(query_data.weapon_only_rgba, mode="RGBA").save(
            weapon_only_path
        )
        Image.fromarray(query_data.weapon_only_mask, mode="L").save(mask_path)

        if slot_result.is_unmatched:
            unmatched_count += 1

        rows.append(
            {
                "slot": slot,
                "predicted_weapon": slot_result.predicted_weapon,
                "predicted_score": predicted_score,
                "is_unmatched": slot_result.is_unmatched,
                "threshold": _resolve_threshold(
                    slot_result=slot_result,
                    candidates=candidates,
                ),
                "top_candidates": [
                    _to_candidate_row(item) for item in candidates
                ],
                "saved_slot": _as_path_string(slot_image_path),
                "saved_weapon_only": _as_path_string(weapon_only_path),
                "saved_mask": _as_path_string(mask_path),
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
    candidate: SlotDebugCandidate | None,
) -> dict[str, object] | None:
    if candidate is None:
        return None
    return {
        "weapon": candidate.weapon,
        "score": candidate.score,
        "threshold": candidate.threshold,
    }


def _resolve_threshold(
    *,
    slot_result: WeaponSlotResult,
    candidates: tuple[SlotDebugCandidate, ...],
) -> float | None:
    predicted = _find_candidate_by_weapon(
        candidates=candidates,
        weapon=slot_result.predicted_weapon,
    )
    if predicted is not None:
        return predicted.threshold
    if not candidates:
        return None
    return candidates[0].threshold


def _resolve_predicted_score(
    *,
    slot_result: WeaponSlotResult,
    candidates: tuple[SlotDebugCandidate, ...],
) -> float | None:
    predicted = _find_candidate_by_weapon(
        candidates=candidates,
        weapon=slot_result.predicted_weapon,
    )
    if predicted is not None:
        return predicted.score
    if not candidates:
        return None
    return candidates[0].score


def _resolve_top1_weapon_for_file_name(
    *,
    slot_result: WeaponSlotResult,
    top1: SlotDebugCandidate | None,
) -> str:
    if top1 is not None:
        return top1.weapon
    return slot_result.predicted_weapon


def _resolve_top1_score_for_file_name(
    *,
    top1: SlotDebugCandidate | None,
) -> float | None:
    if top1 is None:
        return None
    return top1.score


def _find_candidate_by_weapon(
    *,
    candidates: tuple[SlotDebugCandidate, ...],
    weapon: str,
) -> SlotDebugCandidate | None:
    for candidate in candidates:
        if candidate.weapon == weapon:
            return candidate
    return None


def _build_slot_file_tag(
    *,
    slot: str,
    top1_weapon: str,
    top1_score: float | None,
) -> str:
    weapon = _sanitize_trace_id(top1_weapon)
    if top1_score is None:
        score = "na"
    else:
        score = f"{top1_score:.4f}"
    return f"{slot}_pred_{weapon}_score_{score}"


def _as_path_string(path: Path) -> str:
    return path.resolve().as_posix()
