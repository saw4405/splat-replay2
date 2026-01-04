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
def client() -> Iterator[TestClient]:
    """FastAPI TestClient のフィクスチャ。

    全 integration テストで使用する。
    """
    container = configure_container()
    app = create_app(container)
    with TestClient(app) as test_client:
        yield test_client
