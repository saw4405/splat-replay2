from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast

import numpy as np
import pytest
from splat_replay.application.interfaces import (
    WeaponCandidateScore,
    WeaponSlotResult,
)
from splat_replay.infrastructure.adapters.weapon_detection import (
    constants,
    unmatched_report,
)
from splat_replay.infrastructure.adapters.weapon_detection.query_builder import (
    QuerySlotData,
)


class _SummaryRow(TypedDict):
    slot: str
    saved_slot: str
    saved_weapon_only: str
    saved_mask: str


class _SummaryJson(TypedDict):
    rows: list[_SummaryRow]


def _build_query_data() -> QuerySlotData:
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    gray = np.zeros((4, 4), dtype=np.uint8)
    return QuerySlotData(
        rgba=rgba,
        gray=gray,
        padded_gray=gray,
        weapon_only_rgba=rgba,
        weapon_only_mask=gray,
    )


def _build_query_data_by_slot() -> dict[str, QuerySlotData]:
    return {slot: _build_query_data() for slot in constants.SLOT_ORDER}


def _build_default_slot_results() -> dict[str, WeaponSlotResult]:
    return {
        slot: WeaponSlotResult(
            slot=slot,
            predicted_weapon=constants.UNKNOWN_WEAPON_LABEL,
            is_unmatched=True,
            top_candidates=(),
        )
        for slot in constants.SLOT_ORDER
    }


def _load_summary(output_dir: str) -> _SummaryJson:
    summary_path = Path(output_dir) / "summary.json"
    return cast(
        _SummaryJson,
        json.loads(summary_path.read_text(encoding="utf-8")),
    )


@pytest.mark.parametrize(
    ("slot_result", "debug_candidates", "expected_weapon", "expected_score"),
    [
        (
            WeaponSlotResult(
                slot="ally_1",
                predicted_weapon="候補B",
                is_unmatched=False,
                top_candidates=(
                    WeaponCandidateScore(
                        weapon="候補A",
                        score=0.95,
                        threshold=0.90,
                    ),
                    WeaponCandidateScore(
                        weapon="候補B",
                        score=0.88,
                        threshold=0.70,
                    ),
                ),
                detected_score=0.88,
            ),
            (
                unmatched_report.SlotDebugCandidate(
                    weapon="候補A",
                    score=0.95,
                    threshold=0.90,
                ),
                unmatched_report.SlotDebugCandidate(
                    weapon="候補B",
                    score=0.88,
                    threshold=0.70,
                ),
            ),
            "候補B",
            "0.8800",
        ),
        (
            WeaponSlotResult(
                slot="ally_1",
                predicted_weapon=constants.UNKNOWN_WEAPON_LABEL,
                is_unmatched=True,
                top_candidates=(
                    WeaponCandidateScore(
                        weapon="候補A",
                        score=0.95,
                        threshold=0.90,
                    ),
                ),
            ),
            (
                unmatched_report.SlotDebugCandidate(
                    weapon="候補A",
                    score=0.95,
                    threshold=0.90,
                ),
            ),
            "候補A",
            "0.9500",
        ),
    ],
)
def test_save_unmatched_slots_uses_expected_weapon_and_score_for_file_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    slot_result: WeaponSlotResult,
    debug_candidates: tuple[unmatched_report.SlotDebugCandidate, ...],
    expected_weapon: str,
    expected_score: str,
) -> None:
    monkeypatch.setattr(constants, "UNMATCHED_OUTPUT_DIR", tmp_path)
    slot_results = _build_default_slot_results()
    slot_results["ally_1"] = slot_result
    slot_debug_candidates_by_slot = {slot: () for slot in constants.SLOT_ORDER}
    slot_debug_candidates_by_slot["ally_1"] = debug_candidates

    output_dir = unmatched_report.save_unmatched_slots(
        frame=np.zeros((8, 8, 3), dtype=np.uint8),
        query_data_by_slot=_build_query_data_by_slot(),
        slot_results=slot_results,
        slot_debug_candidates_by_slot=slot_debug_candidates_by_slot,
        trace_id="test",
    )

    summary = _load_summary(output_dir)
    row = next(item for item in summary["rows"] if item["slot"] == "ally_1")
    saved_slot_name = Path(row["saved_slot"]).name
    saved_weapon_only_name = Path(row["saved_weapon_only"]).name
    saved_mask_name = Path(row["saved_mask"]).name

    assert f"{expected_weapon}_score_{expected_score}" in saved_slot_name
    assert (
        f"{expected_weapon}_score_{expected_score}" in saved_weapon_only_name
    )
    assert f"{expected_weapon}_score_{expected_score}" in saved_mask_name
