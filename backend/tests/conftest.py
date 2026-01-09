from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from splat_replay.bootstrap.web_app import create_app
from splat_replay.infrastructure.di import configure_container

if TYPE_CHECKING:
    pass

PerfRecord = dict[str, object]


@pytest.fixture
def perf_recorder() -> Iterator[Callable[[PerfRecord], None]]:
    records: list[PerfRecord] = []

    def _record(entry: PerfRecord) -> None:
        records.append(entry)

    yield _record

    path_str = os.getenv("PERF_RECORD_PATH")
    if not path_str:
        return

    path = Path(path_str)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parent / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for entry in records:
            handle.write(json.dumps(entry) + "\n")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """FastAPI TestClient のフィクスチャ。

    全 integration テストで使用する。
    契約テスト用に OBSRecorderController の録画メソッドをモック化し、
    実際のOBS録画を行わない。
    """
    # OBSRecorderControllerの録画メソッドをモックして実際の録画を防ぐ
    from splat_replay.infrastructure.adapters.obs.recorder_controller import (
        OBSRecorderController,
    )

    async def mock_start(self) -> None:
        """モック: 録画開始（何もしない）"""
        pass

    async def mock_stop(self) -> tuple[Path | None, Path | None]:
        """モック: 録画停止（ダミーの戻り値を返す）"""
        return None, None

    async def mock_pause(self) -> None:
        """モック: 録画一時停止（何もしない）"""
        pass

    async def mock_resume(self) -> None:
        """モック: 録画再開（何もしない）"""
        pass

    # MonkeyPatchでメソッドを差し替え
    monkeypatch.setattr(OBSRecorderController, "start", mock_start)
    monkeypatch.setattr(OBSRecorderController, "stop", mock_stop)
    monkeypatch.setattr(OBSRecorderController, "pause", mock_pause)
    monkeypatch.setattr(OBSRecorderController, "resume", mock_resume)

    container = configure_container()
    app = create_app(container)
    with TestClient(app) as test_client:
        yield test_client
