"""コマンドラインインターフェース定義。"""

from __future__ import annotations

import typer
from pathlib import Path

from splat_replay.domain.services.state_machine import State, StateMachine

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
from typing import Type, TypeVar, cast

from splat_replay.shared.di import configure_container

app = typer.Typer(help="Splat Replay ツール群")


container = configure_container()

T = TypeVar("T")

def resolve(cls: Type[T]) -> T:
    """DI コンテナから型指定付きで依存を取得する。"""
    return cast(T, container.resolve(cls))


def _require_initialized() -> None:
    """他のコマンド実行前に初期化済みか確認する。"""
    sm = resolve(StateMachine)
    if sm.state is State.READINESS_CHECK:
        typer.echo(
            "初期化が完了していません。先に `init` コマンドを実行してください。",
            err=True,
        )
        raise typer.Exit(code=1)


@app.callback()
def main() -> None:
    """Splat Replay CLI のエントリーポイント。"""


@app.command()
def init() -> None:
    """起動準備を行う。"""
    uc = resolve(InitializeEnvironmentUseCase)
    uc.execute()


@app.command()
def record() -> None:
    """録画を開始する。"""
    _require_initialized()
    uc = resolve(RecordBattleUseCase)
    uc.execute()


@app.command()
def pause() -> None:
    """録画を一時停止する。"""
    _require_initialized()
    uc = resolve(PauseRecordingUseCase)
    uc.execute()


@app.command()
def resume() -> None:
    """録画を再開する。"""
    _require_initialized()
    uc = resolve(ResumeRecordingUseCase)
    uc.execute()


@app.command()
def stop() -> None:
    """録画を停止する。"""
    _require_initialized()
    uc = resolve(StopRecordingUseCase)
    uc.execute()


@app.command()
def edit() -> None:
    """録画停止後の動画を編集する。"""
    _require_initialized()
    uc = resolve(ProcessPostGameUseCase)
    uc.execute()


@app.command()
def upload(file_path: Path) -> None:
    """指定した動画を YouTube へアップロードする。"""
    _require_initialized()
    uc = resolve(UploadVideoUseCase)
    result = uc.execute(file_path)
    typer.echo(f"アップロード完了: {result.url}")


@app.command()
def daemon() -> None:
    """録画からアップロードまで自動実行する。"""
    _require_initialized()
    uc = resolve(DaemonUseCase)
    uc.execute()


if __name__ == "__main__":
    app()
