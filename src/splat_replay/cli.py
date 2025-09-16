"""Splat Replay CLI。"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import threading
import time
from asyncio.subprocess import Process
from pathlib import Path

import typer
from structlog.stdlib import BoundLogger

from splat_replay.application.use_cases import AutoUseCase, UploadUseCase
from splat_replay.shared.di import configure_container, resolve
from splat_replay.shared.logger import buffer_console_logs

app = typer.Typer(help="Splat Replay ツール群")

container = configure_container()

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
def serve(
    host: str = typer.Option("127.0.0.1", help="バインドするホスト名"),
    port: int = typer.Option(8000, help="待ち受けポート"),
    reload: bool = typer.Option(
        False, help="ソース変更を監視して自動再起動するかどうか"
    ),
) -> None:
    """FastAPI バックエンドサーバーを起動する。"""

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        logger.error("uvicorn の読み込みに失敗", error=str(exc))
        raise typer.Exit(1) from exc

    logger.info("FastAPI サーバーを起動", host=host, port=port, reload=reload)
    config = uvicorn.Config(
        "splat_replay.interface.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
    server = uvicorn.Server(config)
    server.run()


@app.command()
def dev(
    api_host: str = typer.Option("127.0.0.1", help="バックエンドのホスト名"),
    api_port: int = typer.Option(8000, help="バックエンドのポート番号"),
    frontend_host: str = typer.Option(
        "127.0.0.1", help="フロントエンドのホスト名"
    ),
    frontend_port: int = typer.Option(5173, help="フロントエンドのポート番号"),
) -> None:
    """バックエンドとフロントエンドを同時に起動する。"""

    try:
        asyncio.run(
            _dev(
                api_host=api_host,
                api_port=api_port,
                frontend_host=frontend_host,
                frontend_port=frontend_port,
            )
        )
    except KeyboardInterrupt:
        logger.info("dev コマンドを停止します")
    except RuntimeError as err:
        logger.error("開発サーバーが異常終了", error=str(err))
        raise typer.Exit(1) from err


async def _dev(
    *,
    api_host: str,
    api_port: int,
    frontend_host: str,
    frontend_port: int,
) -> None:
    npm_executable = shutil.which("npm")
    if npm_executable is None:
        raise RuntimeError(
            "npm が見つかりません。Node.js をインストールしてください。"
        )

    project_root = Path(__file__).resolve().parents[2]
    frontend_path = project_root / "frontend"
    if not frontend_path.exists():
        raise RuntimeError(
            f"frontend ディレクトリが見つかりません: {frontend_path}"
        )

    await _install_frontend_dependencies(npm_executable, frontend_path)

    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "splat_replay.interface.api.main:app",
        "--host",
        api_host,
        "--port",
        str(api_port),
        "--reload",
    ]

    frontend_cmd = [
        npm_executable,
        "run",
        "dev",
        "--",
        "--host",
        frontend_host,
        "--port",
        str(frontend_port),
    ]

    frontend_env = os.environ.copy()
    frontend_env.setdefault("VITE_API_BASE", f"http://{api_host}:{api_port}")

    logger.info(
        "バックエンドとフロントエンドを起動",
        api_host=api_host,
        api_port=api_port,
        frontend_host=frontend_host,
        frontend_port=frontend_port,
    )

    backend_proc = await asyncio.create_subprocess_exec(
        *backend_cmd,
        cwd=str(project_root),
    )
    frontend_proc = await asyncio.create_subprocess_exec(
        frontend_cmd[0],
        *frontend_cmd[1:],
        cwd=str(frontend_path),
        env=frontend_env,
    )

    logger.info("起動完了。Ctrl+C で停止します。")

    try:
        await _wait_for_processes(backend_proc, frontend_proc)
    finally:
        await _terminate_processes([backend_proc, frontend_proc])


async def _install_frontend_dependencies(
    npm_executable: str, frontend_path: Path
) -> None:
    node_modules = frontend_path / "node_modules"
    if node_modules.exists():
        return

    logger.info("npm install を実行します", directory=str(frontend_path))
    process = await asyncio.create_subprocess_exec(
        npm_executable,
        "install",
        cwd=str(frontend_path),
    )
    exit_code = await process.wait()
    if exit_code != 0:
        raise RuntimeError("npm install に失敗しました")


async def _wait_for_processes(
    backend_proc: Process, frontend_proc: Process
) -> None:
    backend_task = asyncio.create_task(backend_proc.wait())
    frontend_task = asyncio.create_task(frontend_proc.wait())
    try:
        done, pending = await asyncio.wait(
            [backend_task, frontend_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
    except asyncio.CancelledError:
        backend_task.cancel()
        frontend_task.cancel()
        raise

    for task in pending:
        task.cancel()

    if backend_task in done:
        exit_code = backend_task.result()
        raise RuntimeError(
            f"バックエンドプロセスが停止しました (exit={exit_code})"
        )

    exit_code = frontend_task.result()
    raise RuntimeError(
        f"フロントエンドプロセスが停止しました (exit={exit_code})"
    )


async def _terminate_processes(processes: list[Process]) -> None:
    for proc in processes:
        if proc.returncode is None:
            proc.terminate()

    for proc in processes:
        if proc.returncode is None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()


if __name__ == "__main__":
    app()
