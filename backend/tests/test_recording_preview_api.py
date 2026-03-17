from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from splat_replay.interface.web.routers.recording import (
    create_recording_router,
)

pytestmark = pytest.mark.contract


class _StaticFrameSource:
    def __init__(self, frame: np.ndarray | None) -> None:
        self._frame = frame

    def get_latest(self) -> np.ndarray | None:
        return self._frame


def _build_server(
    frame: np.ndarray | None,
    *,
    preview_mode: str = "live_capture",
) -> Any:
    return SimpleNamespace(
        web_error_handler=SimpleNamespace(
            handle_error=lambda *_args, **_kwargs: None
        ),
        frame_source=_StaticFrameSource(frame),
        logger=SimpleNamespace(warning=lambda *_args, **_kwargs: None),
        preview_mode_resolver=lambda: preview_mode,
    )


def test_get_preview_frame_returns_204_when_no_frame() -> None:
    app = FastAPI()
    app.include_router(create_recording_router(_build_server(None)))

    with TestClient(app) as client:
        response = client.get("/api/recorder/preview-frame")

    assert response.status_code == 204
    assert response.content == b""


def test_get_preview_frame_returns_jpeg_when_frame_exists() -> None:
    frame = np.full((24, 32, 3), fill_value=96, dtype=np.uint8)
    app = FastAPI()
    app.include_router(create_recording_router(_build_server(frame)))

    with TestClient(app) as client:
        response = client.get("/api/recorder/preview-frame")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    assert response.content


def test_get_preview_mode_returns_live_capture_when_test_video_is_not_set() -> (
    None
):
    app = FastAPI()
    app.include_router(
        create_recording_router(
            _build_server(None, preview_mode="live_capture")
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/recorder/preview-mode")

    assert response.status_code == 200
    assert response.json() == {"mode": "live_capture"}


def test_get_preview_mode_returns_video_file_when_test_video_is_set() -> None:
    app = FastAPI()
    app.include_router(
        create_recording_router(_build_server(None, preview_mode="video_file"))
    )

    with TestClient(app) as client:
        response = client.get("/api/recorder/preview-mode")

    assert response.status_code == 200
    assert response.json() == {"mode": "video_file"}
