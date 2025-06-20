"""コマンドラインインターフェース定義。"""

from __future__ import annotations

import typer

from splat_replay.application import (
    ProcessPostGameUseCase,
    RecordBattleUseCase,
    PauseRecordingUseCase,
    ResumeRecordingUseCase,
    StopRecordingUseCase,
    UploadVideoUseCase,
    DaemonUseCase,
)
from splat_replay.shared.di import configure_container

app = typer.Typer(help="Splat Replay ツール群")


container = configure_container()


@app.callback()
def main() -> None:
    """Splat Replay CLI のエントリーポイント。"""


@app.command()
def record() -> None:
    """録画を開始する。"""
    uc = container.resolve(RecordBattleUseCase)
    uc.execute()


@app.command()
def pause() -> None:
    """録画を一時停止する。"""
    uc = container.resolve(PauseRecordingUseCase)
    uc.execute()


@app.command()
def resume() -> None:
    """録画を再開する。"""
    uc = container.resolve(ResumeRecordingUseCase)
    uc.execute()


@app.command()
def stop() -> None:
    """録画を停止する。"""
    uc = container.resolve(StopRecordingUseCase)
    uc.execute()


@app.command()
def edit() -> None:
    """録画済み動画を編集する。"""
    uc = container.resolve(ProcessPostGameUseCase)
    _ = uc


@app.command()
def upload() -> None:
    """動画を YouTube へアップロードする。"""
    uc = container.resolve(UploadVideoUseCase)
    _ = uc


@app.command()
def daemon() -> None:
    """録画からアップロードまで自動実行する。"""
    uc = container.resolve(DaemonUseCase)
    uc.execute()


if __name__ == "__main__":
    app()
