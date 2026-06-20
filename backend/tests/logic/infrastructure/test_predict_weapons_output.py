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
    predict_weapons_output,
)
from splat_replay.infrastructure.adapters.weapon_detection.query_builder import (
    QuerySlotData,
)


class _SummaryRow(TypedDict):
    slot: str
    saved_slot: str


class _SummaryJson(TypedDict):
    input_image: str
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
    ("slot_result", "debug_candidates", "expected_weapon"),
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
                predict_weapons_output.SlotDebugCandidate(
                    weapon="候補A",
                    score=0.95,
                    threshold=0.90,
                ),
                predict_weapons_output.SlotDebugCandidate(
                    weapon="候補B",
                    score=0.88,
                    threshold=0.70,
                ),
            ),
            "候補B",
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
                predict_weapons_output.SlotDebugCandidate(
                    weapon="候補A",
                    score=0.95,
                    threshold=0.90,
                ),
            ),
            "候補A",
        ),
    ],
)
def test_save_predict_weapons_output_uses_expected_slot_and_weapon_for_file_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    slot_result: WeaponSlotResult,
    debug_candidates: tuple[predict_weapons_output.SlotDebugCandidate, ...],
    expected_weapon: str,
) -> None:
    output_root = tmp_path / "predict_weapons"
    output_root.mkdir()
    monkeypatch.setattr(constants, "PREDICT_WEAPONS_OUTPUT_DIR", output_root)
    slot_results = _build_default_slot_results()
    slot_results["ally_1"] = slot_result
    slot_debug_candidates_by_slot = {slot: () for slot in constants.SLOT_ORDER}
    slot_debug_candidates_by_slot["ally_1"] = debug_candidates

    output_dir = predict_weapons_output.save_predict_weapons_output(
        frame=np.zeros((8, 8, 3), dtype=np.uint8),
        query_data_by_slot=_build_query_data_by_slot(),
        slot_results=slot_results,
        slot_debug_candidates_by_slot=slot_debug_candidates_by_slot,
        battle_dir_name="20260322_123456",
    )

    assert output_dir is not None
    summary = _load_summary(output_dir)
    row = next(item for item in summary["rows"] if item["slot"] == "ally_1")
    saved_slot_name = Path(row["saved_slot"]).name

    assert saved_slot_name == f"味方1_{expected_weapon}.png"
    assert "saved_weapon_only" not in row
    assert "saved_mask" not in row


def test_save_predict_weapons_output_skips_output_when_predict_weapons_dir_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        constants,
        "PREDICT_WEAPONS_OUTPUT_DIR",
        tmp_path / "predict_weapons",
    )

    output_dir = predict_weapons_output.save_predict_weapons_output(
        frame=np.zeros((8, 8, 3), dtype=np.uint8),
        query_data_by_slot=_build_query_data_by_slot(),
        slot_results=_build_default_slot_results(),
        slot_debug_candidates_by_slot={
            slot: () for slot in constants.SLOT_ORDER
        },
        battle_dir_name="20260322_123456",
    )

    assert output_dir is None
    assert not (tmp_path / "predict_weapons").exists()


def test_save_predict_weapons_output_saves_only_slot_images_under_battle_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "predict_weapons"
    output_root.mkdir()
    monkeypatch.setattr(constants, "PREDICT_WEAPONS_OUTPUT_DIR", output_root)

    output_dir = predict_weapons_output.save_predict_weapons_output(
        frame=np.zeros((8, 8, 3), dtype=np.uint8),
        query_data_by_slot=_build_query_data_by_slot(),
        slot_results=_build_default_slot_results(),
        slot_debug_candidates_by_slot={
            slot: () for slot in constants.SLOT_ORDER
        },
        battle_dir_name="20260322_123456",
    )

    assert output_dir is not None
    output_path = Path(output_dir)
    assert output_path == output_root / "20260322_123456"
    assert (output_path / "summary.json").exists()
    assert (output_path / "input_frame.png").exists()
    assert list(output_path.glob("*_weapon_only.png")) == []
    assert list(output_path.glob("*_mask.png")) == []

    summary = _load_summary(output_dir)
    assert Path(summary["input_image"]).exists()
    assert Path(summary["input_image"]) == output_path / "input_frame.png"
    assert len(summary["rows"]) == 8
    for row in summary["rows"]:
        assert Path(row["saved_slot"]).exists()
