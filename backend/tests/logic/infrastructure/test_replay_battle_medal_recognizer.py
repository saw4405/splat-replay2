"""replay 用表彰認識アダプタの契約テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from splat_replay.domain.models import as_frame
from splat_replay.infrastructure.adapters.medal_detection.replay_recognizer import (
    ReplayBattleMedalRecognizerAdapter,
)
from splat_replay.infrastructure.filesystem import paths
from splat_replay.infrastructure.test_input import (
    resolve_replay_input_file_path,
)


def _write_replay_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    battle_medals: object | None,
) -> None:
    settings_path = tmp_path / "config" / "settings.toml"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("SPLAT_REPLAY_SETTINGS_FILE", raising=False)
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)
    observations: dict[str, object] = {}
    if battle_medals is not None:
        observations["battle_medals"] = battle_medals
    resolve_replay_input_file_path().write_text(
        json.dumps(
            {
                "video_path": str(tmp_path / "replay.mkv"),
                "observations": observations,
            }
        ),
        encoding="utf-8",
    )


def _frame() -> np.ndarray:
    return as_frame(np.zeros((16, 16, 3), dtype=np.uint8))


@pytest.mark.asyncio
async def test_replay_battle_medal_recognizer_returns_fixture_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_replay_input(
        tmp_path,
        monkeypatch,
        {"gold": 3, "silver": 0},
    )
    recognizer = ReplayBattleMedalRecognizerAdapter()

    assert await recognizer.count_medals(_frame()) == (3, 0)


@pytest.mark.asyncio
async def test_replay_battle_medal_recognizer_rereads_current_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_replay_input(
        tmp_path,
        monkeypatch,
        {"gold": 1, "silver": 2},
    )
    recognizer = ReplayBattleMedalRecognizerAdapter()
    first = await recognizer.count_medals(_frame())
    _write_replay_input(
        tmp_path,
        monkeypatch,
        {"gold": 3, "silver": 0},
    )
    second = await recognizer.count_medals(_frame())

    assert first == (1, 2)
    assert second == (3, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "battle_medals, error",
    [
        (None, "battle_medals"),
        ({"gold": 3}, "キー"),
        ({"gold": True, "silver": 0}, "0 以上の整数"),
        ({"gold": 3, "silver": -1}, "0 以上の整数"),
    ],
)
async def test_replay_battle_medal_recognizer_fails_fast_for_invalid_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    battle_medals: object | None,
    error: str,
) -> None:
    _write_replay_input(tmp_path, monkeypatch, battle_medals)
    recognizer = ReplayBattleMedalRecognizerAdapter()

    with pytest.raises(RuntimeError, match=error):
        await recognizer.count_medals(_frame())
