"""コマンドラインインターフェース定義。"""

from __future__ import annotations

import typer

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
from splat_replay.shared.di import configure_container

app = typer.Typer(help="Splat Replay ツール群")


container = configure_container()


def _require_initialized() -> None:
    """他のコマンド実行前に初期化済みか確認する。"""
    sm = container.resolve(StateMachine)
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
    uc = container.resolve(InitializeEnvironmentUseCase)
    uc.execute()


@app.command()
def record() -> None:
    """録画を開始する。"""
    _require_initialized()
    uc = container.resolve(RecordBattleUseCase)
    uc.execute()


@app.command()
def pause() -> None:
    """録画を一時停止する。"""
    _require_initialized()
    uc = container.resolve(PauseRecordingUseCase)
    uc.execute()


@app.command()
def resume() -> None:
    """録画を再開する。"""
    _require_initialized()
    uc = container.resolve(ResumeRecordingUseCase)
    uc.execute()


@app.command()
def stop() -> None:
    """録画を停止する。"""
    _require_initialized()
    uc = container.resolve(StopRecordingUseCase)
    uc.execute()


@app.command()
def edit() -> None:
    """録画済み動画を編集する。"""
    _require_initialized()
    uc = container.resolve(ProcessPostGameUseCase)
    _ = uc


@app.command()
def upload() -> None:
    """動画を YouTube へアップロードする。"""
    _require_initialized()
    uc = container.resolve(UploadVideoUseCase)
    _ = uc


@app.command()
def daemon() -> None:
    """録画からアップロードまで自動実行する。"""
    _require_initialized()
    uc = container.resolve(DaemonUseCase)
    uc.execute()


if __name__ == "__main__":
    app()
