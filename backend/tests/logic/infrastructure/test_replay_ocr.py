"""replay 用 OCR アダプタの契約テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from splat_replay.domain.models import as_frame
from splat_replay.domain.ports import OCRPurpose
from splat_replay.infrastructure.adapters.text.replay_ocr import (
    ReplayOCRAdapter,
)
from splat_replay.infrastructure.filesystem import paths
from splat_replay.infrastructure.test_input import (
    resolve_replay_input_file_path,
)


def _write_replay_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    observations: dict[str, object],
) -> None:
    settings_path = tmp_path / "config" / "settings.toml"
    settings_path.parent.mkdir(parents=True)
    monkeypatch.delenv("SPLAT_REPLAY_SETTINGS_FILE", raising=False)
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)
    resolve_replay_input_file_path().write_text(
        json.dumps(
            {
                "video_path": str(tmp_path / "replay.mkv"),
                "observations": observations,
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_replay_ocr_returns_the_value_for_the_explicit_purpose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_replay_input(
        tmp_path,
        monkeypatch,
        {
            "ocr": {
                "battle_kill": "13",
                "battle_death": "2",
                "battle_special": "3",
            }
        },
    )
    adapter = ReplayOCRAdapter()
    frame = as_frame(np.zeros((8, 8, 3), dtype=np.uint8))

    kill = await adapter.recognize_text(
        frame,
        ps_mode="SINGLE_LINE",
        whitelist="0123456789",
        purpose=OCRPurpose.BATTLE_KILL,
    )
    death = await adapter.recognize_text(
        frame,
        ps_mode="SINGLE_LINE",
        whitelist="0123456789",
        purpose=OCRPurpose.BATTLE_DEATH,
    )

    assert kill == "13"
    assert death == "2"


@pytest.mark.asyncio
async def test_replay_ocr_fails_fast_for_missing_purpose_or_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_replay_input(
        tmp_path,
        monkeypatch,
        {"ocr": {"battle_kill": "13"}},
    )
    adapter = ReplayOCRAdapter()
    frame = as_frame(np.zeros((8, 8, 3), dtype=np.uint8))

    with pytest.raises(RuntimeError, match="purpose"):
        await adapter.recognize_text(frame)
    with pytest.raises(RuntimeError, match="battle_special"):
        await adapter.recognize_text(
            frame,
            purpose=OCRPurpose.BATTLE_SPECIAL,
        )


@pytest.mark.asyncio
async def test_replay_ocr_rejects_unknown_observation_purpose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_replay_input(
        tmp_path,
        monkeypatch,
        {"ocr": {"not_a_real_purpose": "13"}},
    )
    adapter = ReplayOCRAdapter()
    frame = as_frame(np.zeros((8, 8, 3), dtype=np.uint8))

    with pytest.raises(RuntimeError, match="未知の用途"):
        await adapter.recognize_text(
            frame,
            purpose=OCRPurpose.BATTLE_KILL,
        )
