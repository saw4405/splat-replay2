"""コマンドラインインターフェース定義。"""

from __future__ import annotations

import time
import threading
import typer
from pathlib import Path


from splat_replay.shared.logger import (
    initialize_logger,
    get_logger,
    buffer_console_logs,
)

from splat_replay.domain.services.state_machine import (
    Event,
    StateMachine,
)

from splat_replay.application import (
    ProcessPostGameUseCase,
    RecordBattleUseCase,
    PauseRecordingUseCase,
    ResumeRecordingUseCase,
    StopRecordingUseCase,
    UploadVideoUseCase,
    InitializeEnvironmentUseCase,
    DaemonUseCase,
)
from splat_replay.application.use_cases.check_initialization import (
    CheckInitializationUseCase,
)
from typing import Type, TypeVar, cast

from splat_replay.shared.di import configure_container

app = typer.Typer(help="Splat Replay ツール群")


container = configure_container()
initialize_logger()
logger = get_logger()

T = TypeVar("T")


def resolve(cls: Type[T]) -> T:
    """DI コンテナから型指定付きで依存を取得する。"""
    return cast(T, container.resolve(cls))


def _require_initialized() -> None:
    """他のコマンド実行前に初期化済みか確認する。"""

    uc = resolve(CheckInitializationUseCase)
    if uc.execute():
        return

    typer.echo(
        "初期化が完了していません。先に `init` コマンドを実行してください。",
        err=True,
    )
    raise typer.Exit(code=1)


@app.callback()
def main() -> None:
    """Splat Replay CLI のエントリーポイント。"""
    logger.info("CLI 起動")


@app.command()
def init(
    timeout: float = typer.Option(
        None, help="デバイス接続待ちタイムアウト（秒、未指定で無限）"
    ),
) -> None:
    """起動準備を行う。"""
    logger.info("init コマンド開始", timeout=timeout)
    uc = resolve(InitializeEnvironmentUseCase)
    if not uc.device.is_connected():
        typer.echo(
            "\033[1;33mキャプチャボードをPCに接続してください。\033[0m\n"
        )
    stop_event = threading.Event()

    def animate():
        animation = [
            "(●´・ω・)    ",
            "(●´・ω・)σ   ",
            "(●´・ω・)σσ  ",
            "(●´・ω・)σσσ ",
            "(●´・ω・)σσσσ",
        ]
        print("\033[?25l", end="")  # カーソル非表示
        idx = 0
        try:
            while not stop_event.is_set():
                message = f"\r初期化中... {animation[idx % len(animation)]}"
                print(message, end="", flush=True)
                idx += 1
                time.sleep(0.5)
        finally:
            print("\033[?25h", end="")  # カーソル表示

    with buffer_console_logs():
        anim_thread = threading.Thread(target=animate)
        anim_thread.start()
        try:
            uc.execute(timeout=timeout)
            stop_event.set()
            anim_thread.join()
            print("\r初期化が完了しました。           ")
        except KeyboardInterrupt:
            stop_event.set()
            anim_thread.join()
            print("\r初期化を中断しました。           ")
            raise typer.Exit(1)
        except Exception as e:
            stop_event.set()
            anim_thread.join()
            print(f"\r初期化に失敗しました: {e}")
            raise typer.Exit(code=1)


@app.command()
def record() -> None:
    """録画を開始する。"""
    logger.info("record コマンド開始")
    _require_initialized()
    uc = resolve(RecordBattleUseCase)
    uc.execute()


@app.command()
def pause() -> None:
    """録画を一時停止する。"""
    logger.info("pause コマンド開始")
    _require_initialized()
    uc = resolve(PauseRecordingUseCase)
    uc.execute()


@app.command()
def resume() -> None:
    """録画を再開する。"""
    logger.info("resume コマンド開始")
    _require_initialized()
    uc = resolve(ResumeRecordingUseCase)
    uc.execute()


@app.command()
def stop() -> None:
    """録画を停止する。"""
    logger.info("stop コマンド開始")
    _require_initialized()
    uc = resolve(StopRecordingUseCase)
    uc.execute()


@app.command()
def edit() -> None:
    """録画停止後の動画を編集する。"""
    logger.info("edit コマンド開始")
    _require_initialized()
    uc = resolve(ProcessPostGameUseCase)
    uc.execute()


@app.command()
def upload(file_path: Path) -> None:
    """指定した動画を YouTube へアップロードする。"""
    logger.info("upload コマンド開始", file_path=str(file_path))
    _require_initialized()
    uc = resolve(UploadVideoUseCase)
    result = uc.execute(file_path)
    typer.echo(f"アップロード完了: {result.url}")


@app.command()
def daemon() -> None:
    """録画からアップロードまで自動実行する。"""
    logger.info("daemon コマンド開始")
    _require_initialized()
    uc = resolve(DaemonUseCase)
    uc.execute()


if __name__ == "__main__":
    app()
