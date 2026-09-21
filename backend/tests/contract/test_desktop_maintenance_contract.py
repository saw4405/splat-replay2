"""保留起動中は読み取りだけを許可し、録画・編集を開始しない。"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from splat_replay.bootstrap.web_app import build_web_api_server
from splat_replay.infrastructure.di import configure_container
from splat_replay.interface.gui.desktop_control import DesktopSignals
from splat_replay.interface.web.app_factory import create_app

pytestmark = pytest.mark.contract


def test_held_start_serves_health_but_does_not_start_workers() -> None:
    server = build_web_api_server(configure_container())
    recording = server.auto_recording_use_case_factory()
    recording.start_background: AsyncMock = AsyncMock()
    recording.stop_background: AsyncMock = AsyncMock()
    server.auto_recording_use_case_factory = lambda: recording
    server.auto_process_service.start: AsyncMock = AsyncMock()
    signals = DesktopSignals()
    app = create_app(server)
    app.state.desktop_signals = signals
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert signals.tray_status.value.decode("utf-8").startswith(
            "starting|"
        )
        assert client.post("/api/process/start").status_code == 503
        recording.start_background.assert_not_awaited()
        server.auto_process_service.start.assert_not_awaited()
    recording.stop_background.assert_awaited_once()


def test_quit_after_recorder_stopped_closes_admission() -> None:
    from unittest.mock import Mock

    server = build_web_api_server(configure_container())
    recording = server.auto_recording_use_case_factory()
    recording.start_background: AsyncMock = AsyncMock(
        side_effect=recording._mark_stopped
    )
    recording.stop_background: AsyncMock = AsyncMock()
    server.auto_recording_use_case_factory = lambda: recording
    server.auto_process_service.start: AsyncMock = AsyncMock()
    server.auto_process_service.is_idle: Mock = Mock(return_value=True)
    signals = DesktopSignals()
    signals.activated.set()
    app = create_app(server)
    app.state.desktop_signals = signals
    with TestClient(app) as client:
        signals.quitting.set()
        signals.requested.set()
        assert signals.ready.wait(2), (
            "停止済み録画ループの代わりに終了条件を評価する"
        )
        assert client.post("/api/recorder/enable-auto").status_code == 503
        assert client.get("/api/health").status_code == 200
