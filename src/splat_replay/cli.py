"""Splat Replay CLI。"""

from __future__ import annotations

import asyncio
import threading
import time

import punq
import typer
from structlog.stdlib import BoundLogger

from splat_replay.application.services.system_setup_service import (
    SystemSetupService,
)
from splat_replay.application.use_cases import AutoUseCase, UploadUseCase
from splat_replay.shared.di import configure_container, resolve
from splat_replay.shared.logger import buffer_console_logs

app = typer.Typer(help="Splat Replay ツール群")

# Lazy container and logger initialization
_container: punq.Container | None = None
_logger: BoundLogger | None = None


def get_container() -> punq.Container:
    """Get or create container lazily."""
    global _container
    if _container is None:
        _container = configure_container()
    return _container


def get_logger() -> BoundLogger:
    """Get or create logger lazily."""
    global _logger
    if _logger is None:
        _logger = resolve(get_container(), BoundLogger)
    assert _logger is not None
    return _logger


@app.command()
def auto(
    timeout: float = typer.Option(
        None, help="デバイス接続待ちタイムアウト（秒、未指定で無限）"
    ),
) -> None:
    """録画からアップロードまで自動実行する。"""
    asyncio.run(_auto(timeout))


async def _auto(timeout: float | None = None) -> None:
    logger = get_logger()
    container = get_container()
    logger.info("auto コマンド開始", timeout=timeout)

    def animate(stop_event: threading.Event) -> None:
        """キャプチャデバイス接続待ちアニメーション."""
        animation = [
            "(●´・ω・)    ",
            "(●´・ω・)σ   ",
            "(●´・ω・)σσ  ",
            "(●´・ω・)σσσ ",
            "(●´・ω・)σσσσ",
        ]
        print("\033[?25l", end="")
        idx = 0
        try:
            while not stop_event.is_set():
                message = f"\rキャプチャボード接続待ち... {animation[idx % len(animation)]}"
                print(message, end="", flush=True)
                idx += 1
                time.sleep(0.5)
        finally:
            print("\033[?25h", end="")

    uc = resolve(container, AutoUseCase)

    stop_event = threading.Event()
    thread = threading.Thread(target=animate, args=(stop_event,), daemon=True)
    thread.start()
    with buffer_console_logs():
        await uc.wait_for_device(timeout)
        print("キャプチャボード接続された！ ヽ(*ﾟ▽ﾟ)ﾉ")
    stop_event.set()
    thread.join()

    await uc.execute()


@app.command()
def upload() -> None:
    """動画を編集してアップロードする。"""
    asyncio.run(_upload())


async def _upload() -> None:
    logger = get_logger()
    container = get_container()
    logger.info("upload コマンド開始")
    uc = resolve(container, UploadUseCase)
    await uc.execute()


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", help="Webサーバーのホスト"),
    port: int = typer.Option(8000, help="Webサーバーのポート"),
    dev: bool = typer.Option(
        False, help="開発モード (フロントエンド同時起動)"
    ),
) -> None:
    """Web GUI アプリケーションを起動する。"""
    # Don't initialize logger/container yet for dev mode
    if dev:
        # Start development server with frontend
        from splat_replay.web.dev_server import start_dev_server

        start_dev_server()
        return

    logger = get_logger()
    container = get_container()
    logger.info("Web GUI アプリケーション開始", host=host, port=port)

    try:
        # Start backend only
        import uvicorn

        from splat_replay.application.services import (
            AutoRecorder,
            DeviceChecker,
            ErrorHandler,
            InstallerService,
            RecordingPreparationService,
            SettingsService,
            SystemCheckService,
        )
        from splat_replay.application.use_cases import UploadUseCase
        from splat_replay.infrastructure.adapters import GuiRuntimePortAdapter
        from splat_replay.infrastructure.runtime.runtime import AppRuntime
        from splat_replay.web.server import WebServer

        # Resolve dependencies
        auto_recorder = resolve(container, AutoRecorder)
        device_checker = resolve(container, DeviceChecker)
        recording_preparation_service = resolve(
            container, RecordingPreparationService
        )
        runtime_adapter = resolve(container, GuiRuntimePortAdapter)
        settings_service = resolve(container, SettingsService)
        app_runtime = resolve(container, AppRuntime)
        upload_use_case = resolve(container, UploadUseCase)

        # Create web server
        web_server = WebServer(
            auto_recorder=auto_recorder,
            device_checker=device_checker,
            recording_preparation_service=recording_preparation_service,
            command_dispatcher=runtime_adapter,
            logger=logger,
            settings_service=settings_service,
            event_bus=app_runtime.event_bus,
            upload_use_case=upload_use_case,
            installer_service=resolve(container, InstallerService),
            system_check_service=resolve(container, SystemCheckService),
            system_setup_service=resolve(container, SystemSetupService),
            error_handler=resolve(container, ErrorHandler),
        )

        # Run uvicorn
        uvicorn.run(web_server.app, host=host, port=port)

    except ImportError as e:
        logger.error(f"Web GUI の依存関係が不足しています: {e}")
        typer.echo("Web GUI を使用するには追加の依存関係が必要です。")
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Web GUI アプリケーションでエラーが発生: {e}")
        typer.echo(f"Web GUI アプリケーションの起動に失敗しました: {e}")
        raise typer.Exit(1)


@app.command()
def webview() -> None:
    """pywebviewベースのデスクトップアプリケーションを起動する。"""
    logger = get_logger()
    logger.info("WebView デスクトップアプリケーション開始")

    try:
        from splat_replay.gui.webview_app import SplatReplayWebViewApp

        app_instance = SplatReplayWebViewApp()
        app_instance.run()
    except ImportError as e:
        logger.error(f"WebView の依存関係が不足しています: {e}")
        typer.echo("WebView を使用するには追加の依存関係が必要です。")
        typer.echo("次のコマンドで依存関係をインストールしてください:")
        typer.echo("  uv sync")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        logger.error(f"フロントエンドビルドが見つかりません: {e}")
        typer.echo(str(e))
        typer.echo("\n次のコマンドでフロントエンドをビルドしてください:")
        typer.echo("  cd frontend")
        typer.echo("  npm install")
        typer.echo("  npm run build")
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"WebView アプリケーションでエラーが発生: {e}")
        typer.echo(f"WebView アプリケーションの起動に失敗しました: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
