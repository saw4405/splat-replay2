"""保留起動中は読み取りだけを許可し、録画・編集を開始しない。"""

from threading import Event
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from splat_replay.bootstrap.web_app import build_web_api_server
from splat_replay.infrastructure.di import configure_container
from splat_replay.interface.gui.desktop_control import DesktopSignals
from splat_replay.interface.web.app_factory import create_app

pytestmark = pytest.mark.contract


def test_held_start_serves_health_but_does_not_start_workers() -> None:
    server = build_web_api_server(configure_container())
    server.setup_service.is_installation_completed: Mock = Mock(
        return_value=True
    )
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
    server = build_web_api_server(configure_container())
    server.setup_service.is_installation_completed: Mock = Mock(
        return_value=True
    )
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


def test_recording_waits_for_setup_while_auto_process_starts() -> None:
    server = build_web_api_server(configure_container())
    setup_checked = Event()
    installation_completed = Event()
    recording_started = Event()
    process_started = Event()

    def is_installation_completed() -> bool:
        setup_checked.set()
        return installation_completed.is_set()

    server.setup_service.is_installation_completed: Mock = Mock(
        side_effect=is_installation_completed
    )
    recording = server.auto_recording_use_case_factory()
    recording.start_background: AsyncMock = AsyncMock(
        side_effect=lambda: recording_started.set() or True
    )
    recording.stop_background: AsyncMock = AsyncMock()
    server.auto_recording_use_case_factory = lambda: recording
    server.auto_process_service.start: AsyncMock = AsyncMock(
        side_effect=process_started.set
    )
    signals = DesktopSignals()
    signals.activated.set()
    app = create_app(server)
    app.state.desktop_signals = signals

    with TestClient(app) as client:
        assert setup_checked.wait(2), "セットアップ状態を確認する"
        assert client.get("/api/health").status_code == 200
        assert process_started.wait(2), "後処理サービスは先に開始する"
        assert not recording_started.is_set()

        installation_completed.set()
        assert recording_started.wait(2), "完了後に自動録画を開始する"

    recording.start_background.assert_awaited_once()
    recording.stop_background.assert_awaited_once()
    server.auto_process_service.start.assert_awaited_once()


def test_quit_during_setup_wait_signals_ready_without_starting_recording() -> (
    None
):
    server = build_web_api_server(configure_container())
    setup_checked = Event()
    recording = server.auto_recording_use_case_factory()
    recording.start_background: AsyncMock = AsyncMock()
    recording.stop_background: AsyncMock = AsyncMock()
    server.auto_recording_use_case_factory = lambda: recording
    server.setup_service.is_installation_completed: Mock = Mock(
        side_effect=lambda: setup_checked.set() or False
    )
    server.auto_process_service.start: AsyncMock = AsyncMock()
    signals = DesktopSignals()
    signals.activated.set()
    app = create_app(server)
    app.state.desktop_signals = signals

    with TestClient(app) as client:
        assert setup_checked.wait(2), "セットアップ状態を確認する"
        assert client.get("/api/health").status_code == 200
        signals.quitting.set()
        signals.requested.set()
        assert signals.ready.wait(2), "初回待機中の終了要求を保守判定する"
        recording.start_background.assert_not_awaited()
        assert client.get("/api/health").status_code == 200

    recording.start_background.assert_not_awaited()
    recording.stop_background.assert_awaited_once()
    server.auto_process_service.start.assert_awaited_once()


def test_setup_status_read_error_retries_until_recording_can_start() -> None:
    server = build_web_api_server(configure_container())
    first_read_failed = Event()
    setup_available = Event()
    recording_started = Event()
    process_started = Event()
    read_count = 0

    def is_installation_completed() -> bool:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            first_read_failed.set()
            raise OSError("setup state is temporarily unavailable")
        return setup_available.is_set()

    server.setup_service.is_installation_completed: Mock = Mock(
        side_effect=is_installation_completed
    )
    recording = server.auto_recording_use_case_factory()
    recording.start_background: AsyncMock = AsyncMock(
        side_effect=lambda: recording_started.set() or True
    )
    recording.stop_background: AsyncMock = AsyncMock()
    server.auto_recording_use_case_factory = lambda: recording
    server.auto_process_service.start: AsyncMock = AsyncMock(
        side_effect=process_started.set
    )
    signals = DesktopSignals()
    signals.activated.set()
    app = create_app(server)
    app.state.desktop_signals = signals

    with TestClient(app):
        assert first_read_failed.wait(2), "状態読取が失敗する"
        assert process_started.wait(2), "後処理サービスは独立して動く"
        assert not recording_started.is_set()

        setup_available.set()
        assert recording_started.wait(3), "状態読取の復旧後に開始する"

    recording.start_background.assert_awaited_once()
    recording.stop_background.assert_awaited_once()
    server.auto_process_service.start.assert_awaited_once()


def test_web_start_with_completed_setup_starts_workers_once() -> None:
    server = build_web_api_server(configure_container())
    setup_checked = Event()
    recording_started = Event()
    process_started = Event()
    server.setup_service.is_installation_completed: Mock = Mock(
        side_effect=lambda: setup_checked.set() or True
    )
    recording = server.auto_recording_use_case_factory()
    recording.start_background: AsyncMock = AsyncMock(
        side_effect=lambda: recording_started.set() or True
    )
    recording.stop_background: AsyncMock = AsyncMock()
    server.auto_recording_use_case_factory = lambda: recording
    server.auto_process_service.start: AsyncMock = AsyncMock(
        side_effect=process_started.set
    )
    app = create_app(server)

    with TestClient(app):
        assert setup_checked.wait(2), "完了状態を確認する"
        assert recording_started.wait(2), "Web 起動で自動録画を開始する"
        assert process_started.wait(2), "後処理サービスを開始する"

    server.setup_service.is_installation_completed.assert_called_once()
    recording.start_background.assert_awaited_once()
    recording.stop_background.assert_awaited_once()
    server.auto_process_service.start.assert_awaited_once()


def test_shutdown_cancels_recording_wait_for_setup() -> None:
    server = build_web_api_server(configure_container())
    setup_checked = Event()
    process_started = Event()
    recording = server.auto_recording_use_case_factory()
    recording.start_background: AsyncMock = AsyncMock()
    recording.stop_background: AsyncMock = AsyncMock()
    server.auto_recording_use_case_factory = lambda: recording
    server.setup_service.is_installation_completed: Mock = Mock(
        side_effect=lambda: setup_checked.set() or False
    )
    server.auto_process_service.start: AsyncMock = AsyncMock(
        side_effect=process_started.set
    )
    signals = DesktopSignals()
    signals.activated.set()
    app = create_app(server)
    app.state.desktop_signals = signals

    with TestClient(app):
        assert setup_checked.wait(2), "セットアップ待機へ入る"
        assert process_started.wait(2), "後処理サービスを起動する"

    recording.start_background.assert_not_awaited()
    recording.stop_background.assert_awaited_once()
    server.auto_process_service.start.assert_awaited_once()
