"""Splat Replay CLI。"""

from __future__ import annotations

import typer
from typing import Type, TypeVar, cast
import asyncio
import threading
import time

from splat_replay.shared.di import configure_container
from splat_replay.shared.logger import initialize_logger, get_logger
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
async def auto(
    timeout: float = typer.Option(
        None, help="デバイス接続待ちタイムアウト（秒、未指定で無限）"
    ),
) -> None:
    """録画からアップロードまで自動実行する。"""
    logger.info("auto コマンド開始", timeout=timeout)
    uc = resolve(AutoUseCase)
    sm = resolve(StateMachine)

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
        await ready.wait()
        stop_event.set()
        thread.join()
        print()
        await task
    finally:
        sm.remove_listener(_on_state_change)


@app.command()
async def upload() -> None:
    """動画を編集してアップロードする。"""
    logger.info("upload コマンド開始")
    uc = resolve(UploadUseCase)
    await uc.execute()


if __name__ == "__main__":
    app()
