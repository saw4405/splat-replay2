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
    """predict_weapons 出力用の候補情報。"""

    weapon: str
    score: float
    threshold: float


def save_predict_weapons_output(
    *,
    frame: np.ndarray,
    query_data_by_slot: dict[str, QuerySlotData],
    slot_results: dict[str, WeaponSlotResult],
    slot_debug_candidates_by_slot: dict[str, tuple[SlotDebugCandidate, ...]],
    battle_dir_name: str | None = None,
    target_slots: set[str] | None = None,
) -> str | None:
    """追跡情報を保存し、出力ディレクトリを返す。"""
    _ = target_slots
    output_dir = _prepare_predict_weapons_output_dir(
        battle_dir_name=battle_dir_name
    )
    if output_dir is None:
        return None

    input_frame_path = output_dir / "input_frame.png"
    cv2.imwrite(str(input_frame_path), frame)

    # predict_weapons 出力時は常に全8スロット分を出力
    output_slots = constants.SLOT_ORDER
    rows: list[dict[str, object]] = []
    unmatched_count = 0
    for slot in output_slots:
        slot_result = slot_results[slot]
        query_data = query_data_by_slot[slot]
        candidates = slot_debug_candidates_by_slot.get(slot, ())

        file_name_weapon = _resolve_file_name_weapon(
            slot_result=slot_result,
            candidates=candidates,
        )
        predicted_score = _resolve_predicted_score(
            slot_result=slot_result,
            candidates=candidates,
        )
        file_name = _build_slot_file_name(
            slot=slot,
            weapon=file_name_weapon,
        )

        slot_image_path = output_dir / f"{file_name}.png"
        Image.fromarray(query_data.rgba, mode="RGBA").save(slot_image_path)

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


def should_save_predict_weapons_output() -> bool:
    return constants.PREDICT_WEAPONS_OUTPUT_DIR.is_dir()


def _prepare_predict_weapons_output_dir(
    *, battle_dir_name: str | None
) -> Path | None:
    output_root = constants.PREDICT_WEAPONS_OUTPUT_DIR
    if not output_root.is_dir():
        return None

    if battle_dir_name is None:
        base_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    else:
        base_name = _sanitize_trace_id(battle_dir_name)
        if not base_name:
            base_name = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = output_root / base_name
    suffix = 2
    while output_dir.exists():
        output_dir = output_root / f"{base_name}_{suffix}"
        suffix += 1
    output_dir.mkdir(parents=False, exist_ok=False)
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
    if not slot_result.is_unmatched and slot_result.detected_score is not None:
        return slot_result.detected_score
    predicted = _find_candidate_by_weapon(
        candidates=candidates,
        weapon=slot_result.predicted_weapon,
    )
    if predicted is not None:
        return predicted.score
    if not candidates:
        return None
    return candidates[0].score


def _resolve_file_name_weapon(
    *,
    slot_result: WeaponSlotResult,
    candidates: tuple[SlotDebugCandidate, ...],
) -> str:
    top1 = candidates[0] if candidates else None
    if slot_result.is_unmatched:
        if top1 is not None:
            return top1.weapon
        return slot_result.predicted_weapon

    return slot_result.predicted_weapon


def _find_candidate_by_weapon(
    *,
    candidates: tuple[SlotDebugCandidate, ...],
    weapon: str,
) -> SlotDebugCandidate | None:
    for candidate in candidates:
        if candidate.weapon == weapon:
            return candidate
    return None


def _build_slot_file_name(
    *,
    slot: str,
    weapon: str,
) -> str:
    slot_label = _build_slot_label(slot)
    weapon_tag = _sanitize_trace_id(weapon)
    return f"{slot_label}_{weapon_tag}"


def _build_slot_label(slot: str) -> str:
    team, _, number = slot.partition("_")
    if number.isdigit():
        if team == "ally":
            return f"味方{number}"
        if team == "enemy":
            return f"敵{number}"
    return _sanitize_trace_id(slot)


def _as_path_string(path: Path) -> str:
    return path.resolve().as_posix()
