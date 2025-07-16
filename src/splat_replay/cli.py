"""Splat Replay CLI。"""

from __future__ import annotations

import typer
from typing import Type, TypeVar, cast
import asyncio
import threading
import time

from splat_replay.shared.di import configure_container
from splat_replay.shared.logger import initialize_logger, get_logger, buffer_console_logs
from splat_replay.application import AutoUseCase, UploadUseCase
from splat_replay.domain.services.state_machine import StateMachine, State

app = typer.Typer(help="Splat Replay ツール群")

container = configure_container()
initialize_logger()
logger = get_logger()

T = TypeVar("T")


def resolve(cls: Type[T]) -> T:
    """DI コンテナから依存を取得する。"""
    return cast(T, container.resolve(cls))


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
    try:
        uc = resolve(AutoUseCase)
        sm = resolve(StateMachine)
    except Exception as e:  # pragma: no cover - 環境依存エラーを無視
        logger.error("依存関係の解決に失敗しました: %s", e)
        return

    ready = asyncio.Event()

    def _on_state_change(state: State) -> None:
        if state not in {State.WAITING_DEVICE, State.OBS_STARTING}:
            ready.set()

    def _animate(stop_event: threading.Event) -> None:
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
                message = f"\r初期化中... {animation[idx % len(animation)]}"
                print(message, end="", flush=True)
                idx += 1
                time.sleep(0.5)
        finally:
            print("\033[?25h", end="")

    sm.add_listener(_on_state_change)
    try:
        task = asyncio.create_task(uc.execute(timeout))
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_animate, args=(stop_event,), daemon=True
        )
        thread.start()
        with buffer_console_logs():
            await ready.wait()
        stop_event.set()
        thread.join()
        print()
        await task
    finally:
        sm.remove_listener(_on_state_change)


@app.command()
def upload() -> None:
    """動画を編集してアップロードする。"""
    asyncio.run(_upload())


async def _upload() -> None:
    logger.info("upload コマンド開始")
    uc = resolve(UploadUseCase)
    await uc.execute()


if __name__ == "__main__":
    app()
