from __future__ import annotations

import multiprocessing
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import httpx
import pytest

from splat_replay.interface.gui import webview_app
from splat_replay.interface.gui.webview_app import (
    SplatReplayWebViewApp,
    build_frontend_entry_url,
    resolve_backend_hosts,
)


def test_build_frontend_entry_url_uses_index_mtime_cache_buster(
    tmp_path: Path,
) -> None:
    """frontend の entry URL は index.html 更新で変化する。"""
    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    index_html = frontend_dist / "index.html"
    index_html.write_text(
        "<!doctype html><title>fresh</title>", encoding="utf-8"
    )

    url = build_frontend_entry_url("http://127.0.0.1:8000", frontend_dist)

    assert url == (
        "http://127.0.0.1:8000/?frontend="
        f"{index_html.stat().st_mtime_ns}-{index_html.stat().st_size}"
    )


def test_resolve_backend_hosts_keeps_webview_on_loopback_when_remote_enabled() -> (
    None
):
    bind_host, browser_host = resolve_backend_hosts(remote_access_enabled=True)

    assert bind_host == "0.0.0.0"
    assert browser_host == "127.0.0.1"


def test_resolve_backend_hosts_uses_loopback_when_remote_disabled() -> None:
    bind_host, browser_host = resolve_backend_hosts(
        remote_access_enabled=False
    )

    assert bind_host == "127.0.0.1"
    assert browser_host == "127.0.0.1"


def test_startup_loads_frontend_after_backend_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = Mock()
    backend_process = Mock()
    logger = Mock()
    stop_event = threading.Event()
    monkeypatch.setattr(
        webview_app, "wait_for_backend", lambda *args, **kwargs: True
    )

    webview_app._load_frontend_when_ready(
        window,
        backend_process,
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8000/?frontend=1-1",
        stop_event,
        logger,
    )

    window.load_url.assert_called_once_with(
        "http://127.0.0.1:8000/?frontend=1-1"
    )
    window.load_html.assert_not_called()


def test_startup_shows_error_when_backend_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = Mock()
    backend_process = Mock()
    backend_process.is_alive.return_value = True
    logger = Mock()
    stop_event = threading.Event()
    monkeypatch.setattr(
        webview_app, "wait_for_backend", lambda *args, **kwargs: False
    )

    webview_app._load_frontend_when_ready(
        window,
        backend_process,
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8000/?frontend=1-1",
        stop_event,
        logger,
    )

    # 応答が遅いだけで録画処理を強制停止しない。
    backend_process.terminate.assert_not_called()
    window.load_html.assert_called_once_with(webview_app._STARTUP_ERROR_HTML)


def test_startup_does_not_update_closed_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = Mock()
    backend_process = Mock()
    logger = Mock()
    stop_event = threading.Event()
    stop_event.set()
    monkeypatch.setattr(
        webview_app, "wait_for_backend", lambda *args, **kwargs: False
    )

    webview_app._load_frontend_when_ready(
        window,
        backend_process,
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8000/?frontend=1-1",
        stop_event,
        logger,
    )

    window.load_url.assert_not_called()
    window.load_html.assert_not_called()
    backend_process.terminate.assert_not_called()


@pytest.mark.parametrize(
    ("cancelled", "process_alive"),
    [(True, True), (False, False)],
)
def test_backend_wait_stops_without_health_request(
    monkeypatch: pytest.MonkeyPatch,
    cancelled: bool,
    process_alive: bool,
) -> None:
    client = MagicMock()
    monkeypatch.setattr(httpx, "Client", Mock(return_value=client))
    stop_event = threading.Event()
    if cancelled:
        stop_event.set()
    backend_process = Mock()
    backend_process.is_alive.return_value = process_alive

    ready = webview_app.wait_for_backend(
        "http://127.0.0.1:8000",
        timeout=1,
        stop_event=stop_event,
        backend_process=backend_process,
        logger=Mock(),
    )

    assert ready is False
    client.__enter__.return_value.get.assert_not_called()


def test_backend_server_stops_gracefully_on_parent_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """親プロセスの終了通知で FastAPI の lifespan を実行できる。"""
    from fastapi import FastAPI

    app = FastAPI()
    monkeypatch.setitem(
        sys.modules,
        "uvicorn.importer",
        SimpleNamespace(import_from_string=lambda path: lambda: app),
    )
    shutdown_event = multiprocessing.Event()
    shutdown_event.set()
    config = Mock()
    server = Mock()
    server.should_exit = False
    config_factory = Mock(return_value=config)
    server_factory = Mock(return_value=server)

    monkeypatch.setitem(
        sys.modules,
        "uvicorn",
        SimpleNamespace(Config=config_factory, Server=server_factory),
    )

    webview_app.start_backend_server(
        "example.app:factory",
        host="127.0.0.2",
        port=9000,
        shutdown_event=shutdown_event,
    )

    deadline = time.monotonic() + 1
    while not server.should_exit and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.should_exit is True
    app_factory = config_factory.call_args.args[0]
    assert app_factory() is app
    assert app.state.desktop_shutdown_event is shutdown_event
    config_factory.assert_called_once_with(
        app_factory,
        host="127.0.0.2",
        port=9000,
        log_level="info",
        access_log=False,
        factory=True,
    )
    server_factory.assert_called_once_with(config)
    server.run.assert_called_once_with()


def test_webview_close_requests_graceful_backend_shutdown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """画面を閉じると、強制終了前にバックエンドへ正常終了を要求する。"""
    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    (frontend_dist / "index.html").write_text("", encoding="utf-8")
    startup_video = tmp_path / "startup.mp4"
    startup_video.write_bytes(b"video")
    window = MagicMock()
    backend_process = MagicMock()
    backend_process.is_alive.return_value = False
    process_factory = Mock(return_value=backend_process)
    monkeypatch.setattr(multiprocessing, "Process", process_factory)
    monkeypatch.setitem(
        sys.modules,
        "webview",
        SimpleNamespace(
            create_window=lambda **kwargs: window,
            start=lambda *args, **kwargs: None,
        ),
    )

    app = SplatReplayWebViewApp(
        project_root=tmp_path,
        startup_video=startup_video,
        logger=Mock(),
        backend_app_module="example.app:factory",
    )
    app.run()

    shutdown_event = process_factory.call_args.kwargs["args"][3]
    assert shutdown_event.is_set()
    backend_process.join.assert_called_once_with(timeout=30)
    backend_process.terminate.assert_not_called()
    backend_process.kill.assert_not_called()
