"""Development server launcher for frontend and backend."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

WINDOWS_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)


@dataclass(frozen=True)
class DevLaunchSpec:
    title: str
    working_dir: Path
    command: list[str]


def _project_root() -> Path:
    # backend/src/splat_replay/bootstrap/dev_server.py から5階層上が
    # リポジトリルート
    return Path(__file__).resolve().parents[4]


def _build_frontend_dev_command(*, windows: bool) -> list[str]:
    return ["npm.cmd" if windows else "npm", "run", "dev"]


def _build_backend_dev_command() -> list[str]:
    return [
        "uv",
        "run",
        "python",
        "-m",
        "uvicorn",
        "splat_replay.bootstrap.web_app:app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
    ]


def _escape_powershell_literal(value: str) -> str:
    return value.replace("'", "''")


def _quote_powershell_token(token: str) -> str:
    if token == "":
        return "''"

    if any(character.isspace() for character in token) or "'" in token:
        return f"'{_escape_powershell_literal(token)}'"

    return token


def _format_powershell_command(spec: DevLaunchSpec) -> str:
    title = _escape_powershell_literal(spec.title)
    working_dir = _escape_powershell_literal(spec.working_dir.as_posix())
    command = " ".join(
        _quote_powershell_token(token) for token in spec.command
    )
    return (
        f"$Host.UI.RawUI.WindowTitle = '{title}'; "
        f"Set-Location -LiteralPath '{working_dir}'; "
        f"{command}"
    )


def build_windows_dev_launch_specs(
    repo_root: Path,
) -> tuple[DevLaunchSpec, ...]:
    return (
        DevLaunchSpec(
            title="Splat Replay Frontend Dev",
            working_dir=repo_root / "frontend",
            command=_build_frontend_dev_command(windows=True),
        ),
        DevLaunchSpec(
            title="Splat Replay Backend Dev",
            working_dir=repo_root / "backend",
            command=_build_backend_dev_command(),
        ),
    )


def launch_windows_dev_servers(repo_root: Path) -> None:
    for spec in build_windows_dev_launch_specs(repo_root):
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoExit",
                "-Command",
                _format_powershell_command(spec),
            ],
            creationflags=WINDOWS_NEW_CONSOLE,
        )

    print("\n" + "=" * 60)
    print("開発サーバー用の PowerShell を起動しました")
    print("=" * 60)
    print("Frontend: http://127.0.0.1:5173")
    print("Backend:  http://127.0.0.1:8000")
    print("API docs: http://127.0.0.1:8000/docs")
    print("=" * 60)
    print("必要に応じて各ウィンドウで Ctrl+C を押して停止してください\n")


def _ensure_frontend_dependencies(frontend_dir: Path) -> None:
    node_modules = frontend_dir / "node_modules"
    if node_modules.exists():
        return

    print("依存関係をインストール中...")
    try:
        subprocess.run(
            ["npm.cmd", "install"] if os.name == "nt" else ["npm", "install"],
            cwd=frontend_dir,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        print(f"エラー: npm installに失敗しました: {error}")
        sys.exit(1)


def _start_non_windows_dev_server(
    frontend_dir: Path,
    backend_dir: Path,
) -> None:
    print("フロントエンド開発サーバーを起動中...")
    try:
        frontend_process = subprocess.Popen(
            _build_frontend_dev_command(windows=False),
            cwd=frontend_dir,
        )
    except Exception as error:
        print(f"エラー: フロントエンドサーバーの起動に失敗しました: {error}")
        sys.exit(1)

    time.sleep(2)

    print("バックエンドサーバーを起動中...")
    try:
        backend_process = subprocess.Popen(
            _build_backend_dev_command(),
            cwd=backend_dir,
        )
    except Exception as error:
        print(f"エラー: バックエンドサーバーの起動に失敗しました: {error}")
        frontend_process.terminate()
        sys.exit(1)

    print("\n" + "=" * 60)
    print("開発サーバーが起動しました!")
    print("=" * 60)
    print("フロントエンド: http://localhost:5173")
    print("バックエンド:     http://localhost:8000")
    print("API ドキュメント: http://localhost:8000/docs")
    print("=" * 60)
    print("終了するには Ctrl+C を押してください\n")

    try:
        frontend_process.wait()
        backend_process.wait()
    except KeyboardInterrupt:
        print("\nサーバーを停止中...")
        frontend_process.terminate()
        backend_process.terminate()
        try:
            frontend_process.wait(timeout=5)
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            frontend_process.kill()
            backend_process.kill()
        print("サーバーが停止しました")


def start_dev_server() -> None:
    """Start both frontend (Vite) and backend (FastAPI) servers."""
    repo_root = _project_root()
    frontend_dir = repo_root / "frontend"
    backend_dir = repo_root / "backend"

    if not frontend_dir.exists():
        print(
            f"エラー: フロントエンドディレクトリが見つかりません: {frontend_dir}"
        )
        sys.exit(1)

    if not backend_dir.exists():
        print(
            f"エラー: バックエンドディレクトリが見つかりません: {backend_dir}"
        )
        sys.exit(1)

    _ensure_frontend_dependencies(frontend_dir)

    if os.name == "nt":
        launch_windows_dev_servers(repo_root)
        return

    _start_non_windows_dev_server(frontend_dir, backend_dir)


if __name__ == "__main__":
    start_dev_server()
