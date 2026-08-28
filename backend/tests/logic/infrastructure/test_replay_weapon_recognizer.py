"""replay 用ブキ認識アダプタの契約テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from splat_replay.application.interfaces import WeaponSlotResult
from splat_replay.domain.models import as_frame
from splat_replay.infrastructure.adapters.weapon_detection.replay_recognizer import (
    ReplayWeaponRecognitionAdapter,
)
from splat_replay.infrastructure.filesystem import paths
from splat_replay.infrastructure.test_input import (
    REPLAY_WEAPON_SLOT_NAMES,
    resolve_replay_input_file_path,
)


def _weapon_observations(
    weapons: dict[str, str],
    *,
    display_visible: bool = True,
    should_recognize: bool = True,
) -> dict[str, object]:
    return {
        "weapon_recognition": {
            "display": {
                "is_visible": display_visible,
                "should_recognize": should_recognize,
            },
            "slots": {
                slot: {"weapon": weapons[slot], "matched": True}
                for slot in REPLAY_WEAPON_SLOT_NAMES
            },
        }
    }


def _write_replay_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    observations: dict[str, object] | None,
) -> None:
    settings_path = tmp_path / "config" / "settings.toml"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)
    payload: dict[str, object] = {"video_path": str(tmp_path / "replay.mkv")}
    if observations is not None:
        payload["observations"] = observations
    resolve_replay_input_file_path().write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _frame() -> np.ndarray:
    return as_frame(np.zeros((16, 16, 3), dtype=np.uint8))


@pytest.mark.asyncio
async def test_replay_recognizer_returns_fixture_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    weapons = {
        "ally_1": "トライストリンガー",
        "ally_2": "52ガロン",
        "ally_3": "カーボンローラーデコ",
        "ally_4": "スパッタリー・ヒュー",
        "enemy_1": "LACT-450デコ",
        "enemy_2": "スプラチャージャーコラボ",
        "enemy_3": "ノーチラス79",
        "enemy_4": "ホットブラスターカスタム",
    }
    _write_replay_input(
        tmp_path,
        monkeypatch,
        _weapon_observations(weapons),
    )
    recognizer = ReplayWeaponRecognitionAdapter()

    display = await recognizer.detect_weapon_display_details(_frame())
    recognized = await recognizer.recognize_weapons(_frame())

    assert display.is_visible is True
    assert display.should_recognize is True
    assert display.reason == "replay_observation"
    assert recognized.allies == (
        "トライストリンガー",
        "52ガロン",
        "カーボンローラーデコ",
        "スパッタリー・ヒュー",
    )
    assert recognized.enemies == (
        "LACT-450デコ",
        "スプラチャージャーコラボ",
        "ノーチラス79",
        "ホットブラスターカスタム",
    )
    assert all(not result.is_unmatched for result in recognized.slot_results)
    assert all(result.best_score == 1.0 for result in recognized.slot_results)


@pytest.mark.asyncio
async def test_replay_recognizer_preserves_previous_non_target_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    weapons = {slot: f"weapon-{slot}" for slot in REPLAY_WEAPON_SLOT_NAMES}
    _write_replay_input(
        tmp_path,
        monkeypatch,
        _weapon_observations(weapons),
    )
    recognizer = ReplayWeaponRecognitionAdapter()
    previous = WeaponSlotResult(
        slot="ally_1",
        predicted_weapon="前回のブキ",
        is_unmatched=False,
        top_candidates=(),
        detected_score=0.5,
    )

    recognized = await recognizer.recognize_weapons(
        _frame(),
        target_slots={"enemy_1"},
        previous_results={"ally_1": previous},
    )

    result_by_slot = {
        result.slot: result for result in recognized.slot_results
    }
    assert result_by_slot["ally_1"] == previous
    assert result_by_slot["enemy_1"].predicted_weapon == "weapon-enemy_1"
    assert result_by_slot["enemy_1"].is_unmatched is False
    assert result_by_slot["ally_2"].predicted_weapon == "不明"
    assert result_by_slot["ally_2"].is_unmatched is True


@pytest.mark.asyncio
async def test_replay_recognizer_rereads_the_current_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_weapons = {
        slot: f"initial-{slot}" for slot in REPLAY_WEAPON_SLOT_NAMES
    }
    updated_weapons = {
        slot: f"updated-{slot}" for slot in REPLAY_WEAPON_SLOT_NAMES
    }
    _write_replay_input(
        tmp_path,
        monkeypatch,
        _weapon_observations(initial_weapons),
    )
    recognizer = ReplayWeaponRecognitionAdapter()
    first = await recognizer.recognize_weapons(_frame())
    _write_replay_input(
        tmp_path,
        monkeypatch,
        _weapon_observations(updated_weapons),
    )
    second = await recognizer.recognize_weapons(_frame())

    assert first.allies[0] == "initial-ally_1"
    assert second.allies[0] == "updated-ally_1"


@pytest.mark.asyncio
async def test_replay_recognizer_fails_fast_when_observation_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_replay_input(tmp_path, monkeypatch, observations=None)
    recognizer = ReplayWeaponRecognitionAdapter()

    with pytest.raises(RuntimeError, match="observations"):
        await recognizer.detect_weapon_display_details(_frame())


@pytest.mark.asyncio
async def test_replay_recognizer_rejects_missing_or_unexpected_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slots = {
        slot: {"weapon": f"weapon-{slot}", "matched": True}
        for slot in REPLAY_WEAPON_SLOT_NAMES
    }
    slots.pop("enemy_4")
    slots["unexpected"] = {"weapon": "unexpected", "matched": True}
    observations: dict[str, object] = {
        "weapon_recognition": {
            "display": {"is_visible": True, "should_recognize": True},
            "slots": slots,
        }
    }
    _write_replay_input(tmp_path, monkeypatch, observations)
    recognizer = ReplayWeaponRecognitionAdapter()

    with pytest.raises(RuntimeError, match="スロット名"):
        await recognizer.recognize_weapons(_frame())


@pytest.mark.asyncio
async def test_replay_recognizer_rejects_invalid_slot_observation_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slots: dict[str, dict[str, object]] = {
        slot: {"weapon": f"weapon-{slot}", "matched": True}
        for slot in REPLAY_WEAPON_SLOT_NAMES
    }
    slots["ally_1"] = {"weapon": "weapon-ally_1", "matched": "true"}
    observations: dict[str, object] = {
        "weapon_recognition": {
            "display": {"is_visible": True, "should_recognize": True},
            "slots": slots,
        }
    }
    _write_replay_input(tmp_path, monkeypatch, observations)
    recognizer = ReplayWeaponRecognitionAdapter()

    with pytest.raises(RuntimeError, match="matched"):
        await recognizer.recognize_weapons(_frame())
