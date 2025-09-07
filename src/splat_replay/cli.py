"""Splat Replay CLI。"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TypeVar

import typer
from structlog.stdlib import BoundLogger

from splat_replay.application.use_cases import AutoUseCase, UploadUseCase
from splat_replay.gui.app import SplatReplayGUI
from splat_replay.shared.di import configure_container, resolve
from splat_replay.shared.logger import buffer_console_logs

app = typer.Typer(help="Splat Replay ツール群")

container = configure_container()

T = TypeVar("T")


logger = resolve(container, BoundLogger)


@app.command()
def auto(
    timeout: float = typer.Option(
        None, help="デバイス接続待ちタイムアウト（秒、未指定で無限）"
    ),
) -> None:
    """録画からアップロードまで自動実行する。"""
    asyncio.run(_auto(timeout))


async def _auto(timeout: float | None = None) -> None:
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
    logger.info("upload コマンド開始")
    uc = resolve(container, UploadUseCase)
    await uc.execute()


@app.command()
def gui() -> None:
    """GUI アプリケーションを起動する。"""
    logger.info("GUI アプリケーション開始")

    try:
        app = SplatReplayGUI()
        app.run()
    except ImportError as e:
        logger.error(f"GUI の依存関係が不足しています: {e}")
        typer.echo("GUI を使用するには追加の依存関係が必要です。")
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"GUI アプリケーションでエラーが発生: {e}")
        typer.echo(f"GUI アプリケーションの起動に失敗しました: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
