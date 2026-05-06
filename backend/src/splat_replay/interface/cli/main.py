"""Splat Replay CLI."""

from __future__ import annotations

import asyncio
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import typer
from fastapi import FastAPI
from structlog.stdlib import BoundLogger

from splat_replay.application.use_cases import AutoUseCase, UploadUseCase
from splat_replay.interface.cli.logging_utils import buffer_console_logs


class WebViewApp(Protocol):
    """Minimal interface for a webview application."""

    def run(self) -> None: ...


@dataclass(frozen=True)
class CliDependencies:
    auto_use_case: Callable[[], AutoUseCase]
    upload_use_case: Callable[[], UploadUseCase]
    logger: Callable[[], BoundLogger]
    web_app: Callable[[], FastAPI]
    webview_app: Callable[[], WebViewApp]
    start_dev_server: Callable[[], None]
    remote_access_enabled: Callable[[], bool]


def resolve_web_bind_host(
    requested_host: str | None,
    remote_access_enabled: bool,
) -> str:
    if requested_host:
        return requested_host
    return "0.0.0.0" if remote_access_enabled else "127.0.0.1"


def build_app(deps: CliDependencies) -> typer.Typer:
    app = typer.Typer(help="Splat Replay ツール群")

    @app.command()
    def auto(
        timeout: float = typer.Option(
            None, help="デバイス接続待ちタイムアウト（秒、未指定で無限）"
        ),
    ) -> None:
        """録画からアップロードまで自動実行する。"""
        asyncio.run(_auto(timeout))

    async def _auto(timeout: float | None = None) -> None:
        logger = deps.logger()
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
                    message = (
                        f"\rキャプチャボード接続待ち... "
                        f"{animation[idx % len(animation)]}"
                    )
                    print(message, end="", flush=True)
                    idx += 1
                    time.sleep(0.5)
            finally:
                print("\033[?25h", end="")

        uc = deps.auto_use_case()

        stop_event = threading.Event()
        thread = threading.Thread(
            target=animate, args=(stop_event,), daemon=True
        )
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
        logger = deps.logger()
        logger.info("upload コマンド開始")
        uc = deps.upload_use_case()
        await uc.execute()

    @app.command()
    def web(
        host: str | None = typer.Option(
            None,
            help="Webサーバーのホスト（未指定ならLAN公開設定に従う）",
        ),
        port: int = typer.Option(8000, help="Webサーバーのポート"),
        dev: bool = typer.Option(
            False, help="開発モード (フロントエンド同時起動)"
        ),
    ) -> None:
        """Web GUI アプリケーションを起動する。"""
        if dev:
            deps.start_dev_server()
            return

        logger = deps.logger()
        bind_host = resolve_web_bind_host(
            requested_host=host,
            remote_access_enabled=deps.remote_access_enabled(),
        )
        logger.info("Web GUI アプリケーション開始", host=bind_host, port=port)

        try:
            import uvicorn

            os.environ["SPLAT_REPLAY_BACKEND_BIND_HOST"] = bind_host
            os.environ["SPLAT_REPLAY_BACKEND_PORT"] = str(port)
            uvicorn.run(deps.web_app(), host=bind_host, port=port)
        except ImportError as e:
            logger.error("Web GUI の依存関係が不足しています", error=str(e))
            typer.echo("Web GUI を使用するには追加の依存関係が必要です。")
            raise typer.Exit(1)
        except Exception as e:
            logger.error(
                "Web GUI アプリケーションでエラーが発生", error=str(e)
            )
            typer.echo(f"Web GUI アプリケーションの起動に失敗しました: {e}")
            raise typer.Exit(1)

    @app.command()
    def webview() -> None:
        """pywebviewベースのデスクトップアプリケーションを起動する。"""
        logger = deps.logger()
        logger.info("WebView デスクトップアプリケーション開始")

        try:
            app_instance = deps.webview_app()
            app_instance.run()
        except ImportError as e:
            logger.error("WebView の依存関係が不足しています", error=str(e))
            typer.echo("WebView を使用するには追加の依存関係が必要です。")
            typer.echo("次のコマンドで依存関係をインストールしてください:")
            typer.echo("  cd backend")
            typer.echo("  uv sync")
            raise typer.Exit(1)
        except FileNotFoundError as e:
            logger.error("フロントエンドビルドが見つかりません", error=str(e))
            typer.echo(str(e))
            typer.echo("\n次のコマンドでフロントエンドをビルドしてください:")
            typer.echo("  cd frontend")
            typer.echo("  npm install")
            typer.echo("  npm run build")
            raise typer.Exit(1)
        except Exception as e:
            logger.error(
                "WebView アプリケーションでエラーが発生", error=str(e)
            )
            typer.echo(f"WebView アプリケーションの起動に失敗しました: {e}")
            raise typer.Exit(1)

    return app


__all__ = ["CliDependencies", "build_app", "resolve_web_bind_host"]
