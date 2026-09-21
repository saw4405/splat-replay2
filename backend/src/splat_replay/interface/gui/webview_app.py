"""pywebview based desktop application.

FastAPIバックエンドとpywebviewフロントエンドを統合したデスクトップアプリ。
"""

from __future__ import annotations

import base64
import multiprocessing
import os
import sys
import threading
import time
import traceback
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import TYPE_CHECKING, cast
from collections.abc import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import structlog
from structlog.stdlib import BoundLogger

from splat_replay.interface.gui.webview_runtime import (
    configure_webview2_browser_arguments,
)
from splat_replay.interface.gui.desktop_control import (
    DesktopControl,
    DesktopSignals,
)

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event as ProcessEvent

    from uvicorn import Server
    import webview


_STARTUP_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Splat Replay</title>
  <style>
    html, body { height: 100%; margin: 0; }
    body {
      display: grid;
      place-items: center;
      overflow: hidden;
      color: rgba(245, 245, 255, 0.95);
      background: linear-gradient(140deg, #090916 0%, #161633 44%, #10263b 100%);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif;
    }
    main { display: grid; justify-items: center; gap: 24px; }
    h1 {
      margin: 0;
      color: #2ff6e3;
      font-size: 48px;
      font-weight: 700;
      line-height: 1.1;
      letter-spacing: 0.05em;
      text-shadow:
        0 0 10px rgba(47, 246, 227, 0.8),
        0 0 20px rgba(47, 246, 227, 0.6),
        0 0 30px rgba(47, 246, 227, 0.4),
        0 0 40px rgba(47, 246, 227, 0.3),
        0 0 60px rgba(47, 246, 227, 0.2),
        0 2px 4px rgba(6, 8, 15, 0.5);
    }
    .loader {
      width: min(512px, calc(100vw - 64px));
      aspect-ratio: 16 / 15;
      object-fit: cover;
    }
    p { margin: 0; color: rgba(220, 224, 247, 0.72); font-size: 18px; }
  </style>
</head>
<body>
  <main role="status" aria-live="polite">
    <h1>Splat Replay</h1>
    <video class="loader" src="data:video/mp4;base64,STARTUP_VIDEO_DATA" autoplay muted loop playsinline preload="auto" aria-hidden="true"></video>
    <p>起動しています...</p>
  </main>
</body>
</html>"""

_STARTUP_ERROR_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Splat Replay - 起動エラー</title>
  <style>
    html, body { height: 100%; margin: 0; }
    body {
      display: grid;
      place-items: center;
      color: rgba(245, 245, 255, 0.95);
      background: linear-gradient(140deg, #090916 0%, #161633 44%, #10263b 100%);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      text-align: center;
    }
    main { max-width: 560px; padding: 32px; }
    h1 { color: #ff5f88; font-size: 32px; }
    p { color: rgba(220, 224, 247, 0.8); font-size: 18px; line-height: 1.7; }
  </style>
</head>
<body>
  <main role="alert">
    <h1>起動に失敗しました</h1>
    <p>アプリを閉じて再度起動してください。解決しない場合は logs フォルダを確認してください。</p>
  </main>
</body>
</html>"""


def find_frontend_dist(project_root: Path) -> Path:
    """フロントエンドdistディレクトリを検索。

    PyInstaller環境では sys._MEIPASS ベースから、
    通常環境ではプロジェクトルートから相対パスで検索。

    Args:
        project_root: プロジェクトルート

    Returns:
        distディレクトリのパス

    Raises:
        FileNotFoundError: distディレクトリが見つからない場合
    """
    # PROJECT_ROOT は PyInstaller 環境にも対応済み
    dist = project_root / "frontend" / "dist"

    if not dist.exists():
        raise FileNotFoundError(
            f"Frontend dist not found at {dist}. "
            "Run 'npm run build' in frontend directory first."
        )

    return dist


def build_frontend_entry_url(backend_url: str, frontend_dist: Path) -> str:
    """frontend の entry HTML 更新時に WebView の HTTP キャッシュを避ける。"""
    index_html = frontend_dist / "index.html"
    index_stat = index_html.stat()
    frontend_version = f"{index_stat.st_mtime_ns}-{index_stat.st_size}"
    parts = urlsplit(backend_url)
    path = parts.path or "/"
    if not path.endswith("/"):
        path = f"{path}/"
    query = urlencode(
        [
            *parse_qsl(parts.query, keep_blank_values=True),
            ("frontend", frontend_version),
        ]
    )
    return urlunsplit(
        (parts.scheme, parts.netloc, path, query, parts.fragment)
    )


def resolve_backend_hosts(remote_access_enabled: bool) -> tuple[str, str]:
    """Return backend bind host and WebView URL host."""
    if remote_access_enabled:
        return "0.0.0.0", "127.0.0.1"
    return "127.0.0.1", "127.0.0.1"


def _request_backend_shutdown(
    shutdown_event: ProcessEvent, server: Server
) -> None:
    """親プロセスからの終了通知を Uvicorn の正常終了へ変換する。"""
    shutdown_event.wait()
    server.should_exit = True


def start_backend_server(
    app_import_path: str,
    host: str = "127.0.0.1",
    port: int = 8000,
    shutdown_event: ProcessEvent | None = None,
    desktop_signals: DesktopSignals | None = None,
) -> None:
    """FastAPIバックエンドサーバーを起動。

    Args:
        app_import_path: uvicorn で起動する ASGI アプリの import パス
        host: バインドするホスト
        port: バインドするポート
        shutdown_event: 親プロセスからの正常終了通知
    """
    logger = structlog.get_logger()

    try:
        import uvicorn

        os.environ["SPLAT_REPLAY_BACKEND_BIND_HOST"] = host
        os.environ["SPLAT_REPLAY_BACKEND_PORT"] = str(port)
        logger.info(
            "Starting FastAPI backend",
            host=host,
            port=port,
            app=app_import_path,
        )

        from uvicorn.importer import import_from_string
        from fastapi import FastAPI

        def desktop_app() -> FastAPI:
            factory = cast(
                Callable[[], FastAPI], import_from_string(app_import_path)
            )
            app = factory()
            app.state.desktop_signals = desktop_signals
            app.state.desktop_shutdown_event = shutdown_event
            return app

        server = uvicorn.Server(
            uvicorn.Config(
                desktop_app
                if desktop_signals is not None or shutdown_event is not None
                else app_import_path,
                host=host,
                port=port,
                log_level="info",
                access_log=False,
                factory=True,
            )
        )
        if shutdown_event is not None:
            threading.Thread(
                target=_request_backend_shutdown,
                args=(shutdown_event, server),
                daemon=True,
                name="backend-shutdown-watcher",
            ).start()
        server.run()
    except Exception as e:
        logger.error("Backend server error", error=str(e), exc_info=True)
        print(f"\n{'=' * 60}")
        print("BACKEND SERVER ERROR:")
        print(f"{'=' * 60}")
        print(f"{type(e).__name__}: {e}")
        print(f"\n{'=' * 60}")
        print("Traceback:")
        print(f"{'=' * 60}")
        traceback.print_exc()
        print(f"{'=' * 60}\n")
        raise


def wait_for_backend(
    url: str,
    timeout: int = 120,
    interval: float = 0.1,
    logger: BoundLogger | None = None,
    stop_event: threading.Event | None = None,
    backend_process: BaseProcess | None = None,
) -> bool:
    """バックエンドサーバーの起動を待機。

    Args:
        url: バックエンドURL
        timeout: タイムアウト秒数
        interval: チェック間隔秒数
        logger: 使用するロガー（未指定時はデフォルト）

    Returns:
        起動成功ならTrue、タイムアウトならFalse
    """
    import httpx

    if logger is None:
        logger = structlog.get_logger()
    logger.info("Waiting for backend to start", url=url, timeout=timeout)

    deadline = time.monotonic() + timeout
    with httpx.Client(verify=False) as client:
        while time.monotonic() < deadline:
            if stop_event is not None and stop_event.is_set():
                logger.info("Backend startup wait cancelled")
                return False
            if backend_process is not None and not backend_process.is_alive():
                logger.error("Backend process exited before startup")
                return False

            try:
                response = client.get(f"{url}/api/health", timeout=2.0)
                if response.status_code == 200:
                    logger.info("Backend is ready", url=url)
                    return True
                logger.warning(
                    "Backend health check failed",
                    status_code=response.status_code,
                )
            except Exception as e:
                logger.debug("Backend not ready yet", error=str(e))

            if stop_event is not None:
                if stop_event.wait(interval):
                    return False
            else:
                time.sleep(interval)

    logger.error("Backend startup timeout", url=url, timeout=timeout)
    return False


def _load_frontend_when_ready(
    window: webview.Window,
    backend_process: BaseProcess,
    backend_url: str,
    frontend_url: str,
    stop_event: threading.Event,
    logger: BoundLogger,
) -> bool:
    """バックエンド準備完了後、起動画面を本画面へ切り替える。"""
    try:
        ready = wait_for_backend(
            backend_url,
            logger=logger,
            stop_event=stop_event,
            backend_process=backend_process,
        )
        if stop_event.is_set():
            return False
        if ready:
            window.load_url(frontend_url)
            return True
        logger.error("Failed to start backend server")
    except Exception as e:
        if stop_event.is_set():
            return False
        logger.error("Startup callback failed", error=str(e), exc_info=True)

    try:
        window.load_html(_STARTUP_ERROR_HTML)
    except Exception as e:
        logger.error(
            "Failed to show startup error", error=str(e), exc_info=True
        )

    return False


class SplatReplayWebViewApp:
    """pywebviewベースのデスクトップアプリケーション。"""

    def __init__(
        self,
        *,
        project_root: Path,
        startup_video: Path,
        logger: BoundLogger,
        backend_app_module: str,
        render_mode: str = "gpu",
        title: str = "Splat Replay",
        width: int = 1200,
        height: int = 900,
        backend_host: str = "127.0.0.1",
        backend_bind_host: str | None = None,
        backend_url_host: str | None = None,
        backend_port: int = 8000,
        desktop_control: DesktopControl | None = None,
        background: bool = False,
        hold: bool = False,
    ) -> None:
        """初期化。

        Args:
            project_root: プロジェクトルート
            startup_video: 起動画面の無音 MP4
            logger: ロガー
            backend_app_module: 起動するバックエンド ASGI アプリの import パス
            render_mode: WebView の描画モード
            title: ウィンドウタイトル
            width: ウィンドウ幅
            height: ウィンドウ高さ
            backend_host: バックエンドホスト
            backend_port: バックエンドポート
        """
        self.project_root = project_root
        self.startup_video = startup_video
        self.logger = logger
        self.backend_app_module = backend_app_module
        self.render_mode = render_mode
        self.title = title
        self.width = width
        self.height = height
        self.backend_host = backend_bind_host or backend_host
        self.backend_url_host = backend_url_host or backend_host
        self.backend_port = backend_port
        self.backend_url = f"http://{self.backend_url_host}:{backend_port}"
        self.desktop_control = desktop_control
        self.background = background
        self.hold = hold

        # フロントエンドパスを検索
        try:
            self.frontend_dist = find_frontend_dist(self.project_root)
        except FileNotFoundError as e:
            self.logger.error(
                "フロントエンドディストリビューションが見つかりません",
                error=str(e),
            )
            raise

    def run(self) -> None:
        """アプリケーションを起動。"""
        self.logger.info(
            "Starting Splat Replay WebView App",
            is_frozen=getattr(sys, "frozen", False),
            project_root=str(self.project_root),
            frontend_dist=str(self.frontend_dist),
        )

        # バックエンドサーバーを別プロセスで起動
        backend_shutdown_event = multiprocessing.Event()
        signals = (
            DesktopSignals() if self.desktop_control is not None else None
        )
        if signals is not None and not self.hold:
            signals.activated.set()
        backend_process = multiprocessing.Process(
            target=start_backend_server,
            args=(
                self.backend_app_module,
                self.backend_host,
                self.backend_port,
                backend_shutdown_event,
                signals,
            ),
            daemon=True,
        )
        backend_process.start()
        tray = None
        stop_event = threading.Event()

        try:
            configured_args = configure_webview2_browser_arguments(
                os.environ,
                platform=sys.platform,
                render_mode=self.render_mode,
            )
            if configured_args is not None:
                self.logger.info(
                    "Configured WebView2 browser arguments",
                    render_mode=self.render_mode,
                    arguments=configured_args,
                )

            import webview

            frontend_url = build_frontend_entry_url(
                self.backend_url, self.frontend_dist
            )
            startup_html = _STARTUP_HTML.replace(
                "STARTUP_VIDEO_DATA",
                base64.b64encode(self.startup_video.read_bytes()).decode(
                    "ascii"
                ),
            )
            window = cast(
                "webview.Window",
                webview.create_window(
                    title=self.title,
                    html=startup_html,
                    width=self.width,
                    height=self.height,
                    resizable=True,
                    min_size=(400, 300),
                    frameless=False,
                    easy_drag=False,
                    background_color="#090916",
                    hidden=self.background or self.hold,
                ),
            )
            exiting = threading.Event()
            backend_verified = threading.Event()

            def on_loaded() -> None:
                if window.get_current_url() == frontend_url:
                    backend_verified.set()

            window.events.loaded += on_loaded
            if self.desktop_control is None:
                window.events.closing += stop_event.set
            else:

                def on_closing() -> bool:
                    if exiting.is_set():
                        stop_event.set()
                        return True
                    window.hide()
                    return False

                window.events.closing += on_closing

                from queue import SimpleQueue
                from splat_replay.interface.gui.desktop_tray import DesktopTray

                commands: SimpleQueue[str] = SimpleQueue()
                tray = DesktopTray(
                    self.startup_video.parent / "icon.ico", commands.put
                )
                tray.start()

                def control_loop() -> None:
                    control = self.desktop_control
                    assert control is not None and signals is not None
                    stopping = False
                    while not stop_event.wait(0.1):
                        for command in (
                            "show",
                            "update",
                            "quit",
                            "cancel",
                            "resume",
                        ):
                            if control.take(command):
                                commands.put(command)
                        while not commands.empty():
                            command = commands.get()
                            if command == "show":
                                window.show()
                            elif command == "resume" and not stopping:
                                signals.activated.set()
                            elif (
                                command in {"update", "quit"} and not stopping
                            ):
                                if command == "quit":
                                    signals.quitting.set()
                                if not signals.requested.is_set():
                                    signals.ready.clear()
                                signals.requested.set()
                                self.logger.info(
                                    "デスクトップ終了要求を受理",
                                    command=command,
                                )
                                control.state("cancelled", False)
                                window.set_title(
                                    "Splat Replay — 処理完了後に終了します"
                                    if signals.quitting.is_set()
                                    else "Splat Replay — Switchのスリープ・後処理完了を待っています"
                                )
                            elif command == "cancel" and not stopping:
                                signals.requested.clear()
                                signals.quitting.clear()
                                control.state("cancelled", True)
                                signals.ready.clear()
                                window.set_title(self.title)
                        control.state("waiting", signals.requested.is_set())
                        control.state(
                            "held",
                            self.hold
                            and backend_verified.is_set()
                            and not signals.activated.is_set(),
                        )
                        control.state(
                            "ready",
                            backend_verified.is_set()
                            and signals.activated.is_set()
                            and not stopping,
                        )
                        if signals.requested.is_set() and (
                            signals.ready.is_set()
                            or not signals.activated.is_set()
                        ):
                            stopping = True
                            backend_shutdown_event.set()
                        status = signals.tray_status.value.decode("utf-8")
                        icon, _, description = status.partition("|")
                        if stopping:
                            icon, description = "starting", "終了処理中"
                        elif not signals.activated.is_set():
                            icon, description = "starting", "更新待機中"
                        elif not status:
                            icon, description = "starting", "起動中"
                        if signals.requested.is_set() and not stopping:
                            description += (
                                "／処理完了後に終了"
                                if signals.quitting.is_set()
                                else "／更新予約中"
                            )
                        tray.set_status(icon, description)
                        if not backend_process.is_alive():
                            exiting.set()
                            window.destroy()
                            return

                threading.Thread(
                    target=control_loop, daemon=True, name="desktop-control"
                ).start()

            def finish_startup() -> None:
                if not _load_frontend_when_ready(
                    window,
                    backend_process,
                    self.backend_url,
                    frontend_url,
                    stop_event,
                    self.logger,
                ):
                    window.show()

            # private_mode=Falseでカメラ許可などの設定を永続化
            webview.start(
                finish_startup,
                debug=False,
                private_mode=False,
            )
            if (
                self.desktop_control is not None
                and backend_process.exitcode not in (None, 0)
            ):
                raise RuntimeError(
                    "バックエンドが異常終了しました。更新を中止します。"
                )

        except Exception as e:
            self.logger.error("WebView error", error=str(e), exc_info=True)
            raise
        finally:
            stop_event.set()
            if tray is not None:
                tray.close()
            # クリーンアップ
            self.logger.info("Requesting graceful backend shutdown")
            backend_shutdown_event.set()
            backend_process.join(timeout=30)
            if self.desktop_control is not None and backend_process.is_alive():
                self.logger.error(
                    "正常終了が完了しないため、更新せず終了を待ちます"
                )
                backend_process.join()
            if backend_process.is_alive():
                self.logger.warning(
                    "Backend did not stop gracefully; force terminating"
                )
                backend_process.terminate()
                backend_process.join(timeout=5)
            if backend_process.is_alive():
                backend_process.kill()


__all__ = [
    "SplatReplayWebViewApp",
    "build_frontend_entry_url",
    "resolve_backend_hosts",
]
