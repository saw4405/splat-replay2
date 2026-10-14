from __future__ import annotations

import multiprocessing
from multiprocessing.synchronize import Event as ProcessEvent
from collections.abc import Callable
import sys
import threading
import time
from queue import Empty, Queue
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, Mock

import httpx
import pytest

from splat_replay.interface.gui.desktop_control import DesktopSignals
from splat_replay.interface.gui import webview_app
from splat_replay.interface.gui.webview_app import (
    SplatReplayWebViewApp,
    _install_macos_camera_permission_delegate,
    _install_macos_graceful_quit_delegate,
    _should_grant_macos_camera_permission,
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


@pytest.mark.parametrize(
    (
        "origin_scheme",
        "origin_host",
        "origin_port",
        "is_main_frame",
        "capture_type",
        "expected",
    ),
    [
        ("http", "127.0.0.1", 8000, True, 1, True),
        ("http", "localhost", 8000, True, 1, False),
        ("https", "127.0.0.1", 8000, True, 1, False),
        ("http", "127.0.0.1", 8001, True, 1, False),
        ("http", "127.0.0.1", 8000, False, 1, False),
        ("http", "127.0.0.1", 8000, True, 2, False),
    ],
)
def test_macos_camera_permission_is_scoped_to_app_main_frame_video(
    origin_scheme: str,
    origin_host: str,
    origin_port: int,
    is_main_frame: bool,
    capture_type: int,
    expected: bool,
) -> None:
    assert (
        _should_grant_macos_camera_permission(
            "http://127.0.0.1:8000",
            origin_scheme,
            origin_host,
            origin_port,
            is_main_frame,
            capture_type,
            camera_capture_type=1,
        )
        is expected
    )


def test_macos_camera_permission_delegate_keeps_other_requests_prompted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = object()

    class NativeDelegate:
        protocols: tuple[object, ...] = (protocol,)
        declared_protocols: object = ()

        def __init_subclass__(cls, **kwargs: object) -> None:
            cls.declared_protocols = kwargs.get("protocols", ())
            super().__init_subclass__()

    browser_view = SimpleNamespace(BrowserDelegate=NativeDelegate)
    cocoa = SimpleNamespace(BrowserView=browser_view)
    webkit = SimpleNamespace(
        WKMediaCaptureTypeCamera=0,
        WKPermissionDecisionGrant=1,
        WKPermissionDecisionPrompt=0,
    )
    monkeypatch.setattr(webview_app.sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "webview.platforms.cocoa", cocoa)
    monkeypatch.setitem(sys.modules, "WebKit", webkit)

    logger = Mock()
    _install_macos_camera_permission_delegate("http://127.0.0.1:8000", logger)

    delegate = browser_view.BrowserDelegate()
    assert delegate.protocols == (protocol,)
    assert delegate.declared_protocols == ()
    decisions: list[int] = []
    origin = SimpleNamespace(
        protocol=lambda: "http",
        host=lambda: "127.0.0.1",
        port=lambda: 8000,
    )
    frame = SimpleNamespace(isMainFrame=lambda: True)
    delegate.webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(
        object(), origin, frame, 0, decisions.append
    )
    assert decisions == [webkit.WKPermissionDecisionGrant]
    logger.info.assert_any_call(
        "Granted camera permission to the packaged WebView origin"
    )

    decisions.clear()
    logger.reset_mock()
    delegate.webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(
        object(), origin, frame, 1, decisions.append
    )
    assert decisions == [webkit.WKPermissionDecisionPrompt]
    logger.info.assert_not_called()


@pytest.mark.parametrize(
    (
        "has_window",
        "should_close",
        "expected_destroy_count",
        "expected_close_count",
    ),
    [(True, False, 0, 1), (True, True, 1, 1), (False, False, 0, 0)],
)
def test_macos_quit_uses_window_close_before_cancelling_app_termination(
    monkeypatch: pytest.MonkeyPatch,
    has_window: bool,
    should_close: bool,
    expected_destroy_count: int,
    expected_close_count: int,
) -> None:
    class NativeDelegate:
        pass

    class Window:
        uid = "main"

    window = Window()
    native_instance = SimpleNamespace(
        pywebview_window=window,
        destroy=Mock(),
    )
    native_should_close = Mock(return_value=int(should_close))
    browser_view = SimpleNamespace(
        AppDelegate=NativeDelegate,
        instances={"main": native_instance} if has_window else {},
        should_close=native_should_close,
    )
    appkit = SimpleNamespace(NSTerminateCancel=0, NSTerminateNow=1)
    monkeypatch.setattr(webview_app.sys, "platform", "darwin")
    monkeypatch.setitem(
        sys.modules,
        "webview.platforms.cocoa",
        SimpleNamespace(BrowserView=browser_view, AppKit=appkit),
    )

    _install_macos_graceful_quit_delegate(Mock())

    result = browser_view.AppDelegate().applicationShouldTerminate_(object())

    assert result == appkit.NSTerminateCancel
    assert native_should_close.call_count == expected_close_count
    if has_window:
        native_should_close.assert_called_once_with(window)
    assert native_instance.destroy.call_count == expected_destroy_count
    if has_window and should_close:
        assert browser_view.should_close(window) == appkit.NSTerminateNow
        native_should_close.assert_called_once_with(window)


def test_macos_resident_quit_and_dock_reopen_enqueue_commands_with_native_signatures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent_quit_signature = b"I@:@"

    class NativeDelegate:
        applicationShouldTerminate_ = SimpleNamespace(
            signature=parent_quit_signature
        )

    selectors: dict[str, bytes] = {}

    def selector(
        function: object, *, selector: bytes, signature: bytes
    ) -> object:
        setattr(function, "native_selector", selector)
        setattr(function, "native_signature", signature)
        selectors[selector.decode()] = signature
        return function

    native_should_close = Mock(
        side_effect=AssertionError("must not close first")
    )
    browser_view = SimpleNamespace(
        AppDelegate=NativeDelegate,
        instances={},
        should_close=native_should_close,
    )
    cocoa = SimpleNamespace(
        BrowserView=browser_view,
        AppKit=SimpleNamespace(NSTerminateCancel=0, NSTerminateNow=1),
    )
    objc = SimpleNamespace(
        selector=selector,
        _C_BOOL=b"B",
    )
    monkeypatch.setattr(webview_app.sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "webview.platforms.cocoa", cocoa)
    monkeypatch.setitem(sys.modules, "objc", objc)
    commands: list[str] = []

    _install_macos_graceful_quit_delegate(
        Mock(), resident=True, command=commands.append
    )
    delegate = browser_view.AppDelegate()

    assert delegate.applicationShouldTerminate_(object()) == 0
    assert (
        delegate.applicationShouldHandleReopen_hasVisibleWindows_(
            object(), False
        )
        is True
    )
    assert commands == ["quit", "show"]
    assert selectors == {
        "applicationShouldTerminate:": parent_quit_signature,
        "applicationShouldHandleReopen:hasVisibleWindows:": b"B@:@B",
    }
    native_should_close.assert_not_called()


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
    monkeypatch.setattr(multiprocessing, "Event", threading.Event)
    monkeypatch.setattr(webview_app.sys, "platform", "linux")
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
    monkeypatch.setattr(
        webview_app, "_install_macos_camera_permission_delegate", Mock()
    )
    monkeypatch.setattr(
        webview_app, "_install_macos_graceful_quit_delegate", Mock()
    )
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


@pytest.mark.parametrize("tray_fails", [False, True])
def test_macos_resident_control_loop_waits_for_backend_before_destroying_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tray_fails: bool,
) -> None:
    """Mac はtray失敗時もcloseを終了予約へつなぎ、処理完了後だけ閉じる。"""
    monkeypatch.setattr(multiprocessing, "Event", threading.Event)
    signals = DesktopSignals()
    monkeypatch.setattr(
        webview_app, "DesktopSignals", Mock(return_value=signals)
    )
    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    (frontend_dist / "index.html").write_text("", encoding="utf-8")
    startup_video = tmp_path / "startup.mp4"
    startup_video.write_bytes(b"video")
    ui_actions: Queue[Callable[[], None]] = Queue()
    allow_backend_ready = threading.Event()
    tray_instances: list[SimpleNamespace] = []

    class EventHook:
        def __init__(self) -> None:
            self.callbacks: list[Callable[..., object]] = []

        def __iadd__(self, callback: Callable[..., object]) -> EventHook:
            self.callbacks.append(callback)
            return self

        def fire(self) -> object:
            assert self.callbacks
            return self.callbacks[-1]()

    class FakeWindow:
        def __init__(self, hidden: bool) -> None:
            self.events = SimpleNamespace(
                loaded=EventHook(), closing=EventHook()
            )
            self.initial_hidden = hidden
            self.hidden = hidden
            self.visible = False
            self.gui_started = False
            self.destroyed = False
            self.destroy_close_allowed = False
            self.method_threads: list[str] = []

        def show(self) -> None:
            assert self.gui_started
            self.method_threads.append(threading.current_thread().name)
            self.visible = True

        def hide(self) -> None:
            assert self.gui_started
            self.method_threads.append(threading.current_thread().name)
            self.visible = False

        def set_title(self, _title: str) -> None:
            assert self.gui_started
            self.method_threads.append(threading.current_thread().name)

        def destroy(self) -> None:
            assert self.gui_started
            self.method_threads.append(threading.current_thread().name)
            self.destroy_close_allowed = self.events.closing.fire() is True
            self.destroyed = True

    windows: list[FakeWindow] = []

    class FakeBackendProcess:
        def __init__(
            self, shutdown: ProcessEvent, signals: DesktopSignals
        ) -> None:
            self.shutdown = shutdown
            self.signals = signals
            self.terminated = False
            self.killed = False
            self.join_calls: list[float | None] = []

        def start(self) -> None:
            pass

        def is_alive(self) -> bool:
            if (
                allow_backend_ready.is_set()
                and self.signals.requested.is_set()
            ):
                self.signals.ready.set()
            return not self.shutdown.is_set()

        @property
        def exitcode(self) -> int | None:
            return 0 if self.shutdown.is_set() else None

        def join(self, timeout: float | None = None) -> None:
            self.join_calls.append(timeout)

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

    processes: list[FakeBackendProcess] = []

    def process_factory(
        *, args: tuple[object, ...], **_kwargs: object
    ) -> FakeBackendProcess:
        process = FakeBackendProcess(
            cast(ProcessEvent, args[3]), cast(DesktopSignals, args[4])
        )
        processes.append(process)
        return process

    class FakeTray:
        def __init__(
            self,
            command: Callable[[str], None],
            _call_after: Callable[[Callable[[], None]], None],
        ) -> None:
            self.command = command
            self.closed = False
            tray_instances.append(SimpleNamespace(instance=self))

        def start(self) -> None:
            if tray_fails:
                raise RuntimeError("simulated status item failure")

        def set_status(self, _state: str, _description: str) -> None:
            pass

        def close(self) -> None:
            self.closed = True

    def create_window(**kwargs: object) -> FakeWindow:
        window = FakeWindow(bool(kwargs["hidden"]))
        windows.append(window)
        return window

    def start_webview(startup: Callable[[], None], **_kwargs: object) -> None:
        window = windows[0]
        window.gui_started = True
        window.visible = not window.hidden
        startup()
        if tray_fails:
            assert window.initial_hidden
            assert not window.hidden
            assert window.visible
            assert window.events.closing.fire() is False
        else:
            assert window.events.closing.fire() is False
            assert not window.visible
            tray_instances[0].instance.command("show")
            pump_until(lambda: window.visible)
        tray_instances[0].instance.command("quit")
        pump_until(lambda: processes[0].signals.requested.is_set())
        assert not processes[0].shutdown.is_set()
        assert not window.destroyed
        allow_backend_ready.set()
        pump_until(lambda: window.destroyed)

    def pump_until(predicate: Callable[[], bool]) -> None:
        deadline = time.monotonic() + 5
        while not predicate():
            remaining = deadline - time.monotonic()
            assert remaining > 0, "GUI/backend event did not arrive"
            try:
                action = ui_actions.get(timeout=min(remaining, 0.05))
            except Empty:
                continue
            assert threading.current_thread() is threading.main_thread()
            action()

    monkeypatch.setattr(webview_app.sys, "platform", "darwin")
    monkeypatch.setattr(multiprocessing, "Process", process_factory)
    monkeypatch.setattr(
        webview_app, "_install_macos_camera_permission_delegate", Mock()
    )
    monkeypatch.setattr(
        webview_app, "_install_macos_graceful_quit_delegate", Mock()
    )
    monkeypatch.setattr(
        webview_app,
        "_load_frontend_when_ready",
        Mock(return_value=True),
    )
    monkeypatch.setitem(
        sys.modules,
        "splat_replay.interface.gui.macos_desktop_tray",
        SimpleNamespace(MacOSDesktopTray=FakeTray),
    )
    monkeypatch.setitem(
        sys.modules,
        "PyObjCTools.AppHelper",
        SimpleNamespace(callAfter=ui_actions.put),
    )
    monkeypatch.setitem(
        sys.modules,
        "webview",
        SimpleNamespace(
            create_window=create_window,
            start=start_webview,
        ),
    )

    app = SplatReplayWebViewApp(
        project_root=tmp_path,
        startup_video=startup_video,
        logger=Mock(),
        backend_app_module="example.app:factory",
        background=tray_fails,
    )
    app.run()

    window = windows[0]
    assert window.destroy_close_allowed
    assert window.method_threads
    assert set(window.method_threads) == {threading.main_thread().name}
    assert processes[0].shutdown.is_set()
    assert processes[0].join_calls == [30]
    assert not processes[0].terminated
    assert not processes[0].killed
    assert tray_instances[0].instance.closed is (not tray_fails)
