"""録画しない検証用 API と実 WebView で、非表示と完全終了を分離する。"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from collections.abc import Callable

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows 専用")


def test_window_close_keeps_resident_until_explicit_quit(
    tmp_path: Path,
) -> None:
    import win32con
    import win32gui
    from splat_replay.infrastructure.adapters.system.desktop_instance import (
        DesktopInstance,
    )

    if not win32gui.FindWindow("Shell_TrayWnd", None):
        pytest.skip("対話デスクトップが必要")
    (tmp_path / "resident_test_api.py").write_text(
        "from fastapi import FastAPI\n"
        "from contextlib import asynccontextmanager\n"
        "def app():\n"
        " @asynccontextmanager\n"
        " async def lifespan(api):\n"
        "  api.state.desktop_signals.started.set()\n"
        "  yield\n"
        " api=FastAPI(lifespan=lifespan)\n"
        " @api.get('/api/health')\n"
        " def health(): return {'status':'ok'}\n"
        " return api\n",
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend/dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("test", encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assets = Path(__file__).resolve().parents[3] / "assets"
    identity = tmp_path / "SplatReplay.exe"
    title = f"SplatReplay resident test {os.getpid()}"
    code = f"""
import sys
from pathlib import Path
import structlog
sys.path.insert(0, {str(tmp_path)!r})
from splat_replay.infrastructure.adapters.system.desktop_instance import DesktopInstance
from splat_replay.interface.gui.webview_app import SplatReplayWebViewApp
instance=DesktopInstance(Path({str(identity)!r}))
try:
 SplatReplayWebViewApp(project_root=Path({str(tmp_path)!r}), startup_video=Path({str(assets / "startup-loading.mp4")!r}), logger=structlog.get_logger(), backend_app_module='resident_test_api:app', backend_port={port}, desktop_control=instance, hold=True, title={title!r}).run()
finally:
 instance.close()
"""

    def wait_until(condition: Callable[[], bool]) -> None:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.1)
        raise AssertionError("常駐 UI の状態遷移が完了しませんでした")

    with (tmp_path / "window.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        client: DesktopInstance | None = None
        try:

            def held() -> bool:
                nonlocal client
                if client is not None:
                    client.close()
                client = DesktopInstance(identity, client_only=True)
                return client.status() == 6

            wait_until(held)
            assert client is not None and client.send("show")
            wait_until(
                lambda: bool(win32gui.FindWindow(None, title))
                and bool(
                    win32gui.IsWindowVisible(win32gui.FindWindow(None, title))
                )
            )
            hwnd = win32gui.FindWindow(None, title)
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            wait_until(lambda: not win32gui.IsWindowVisible(hwnd))
            assert process.poll() is None
            assert client.send("show")
            wait_until(lambda: bool(win32gui.IsWindowVisible(hwnd)))
            assert client.send("quit")
            assert process.wait(timeout=30) == 0
        finally:
            if client is not None:
                client.send("quit")
                client.close()
            if process.poll() is None:
                # このテスト専用の WebView/API だけを回収する。OBS は起動していない。
                process.terminate()
                process.wait(timeout=10)
