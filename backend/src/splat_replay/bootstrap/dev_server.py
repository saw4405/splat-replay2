"""Development server launcher for frontend and backend."""

from __future__ import annotations

import os
import socket
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


@dataclass(frozen=True)
class DevServerNetwork:
    backend_host: str
    frontend_host: str | None
    backend_port: int = 8000
    frontend_port: int = 5173


def _project_root() -> Path:
    # backend/src/splat_replay/bootstrap/dev_server.py から5階層上が
    # リポジトリルート
    return Path(__file__).resolve().parents[4]


def resolve_dev_server_network(
    remote_access_enabled: bool,
) -> DevServerNetwork:
    if remote_access_enabled:
        return DevServerNetwork(
            backend_host="0.0.0.0",
            frontend_host="0.0.0.0",
        )
    return DevServerNetwork(
        backend_host="127.0.0.1",
        frontend_host=None,
    )


def _build_frontend_dev_command(
    *, windows: bool, host: str | None = None
) -> list[str]:
    command = ["npm.cmd" if windows else "npm", "run", "dev"]
    if host is not None:
        command.extend(["--", "--host", host])
    return command


def _build_backend_dev_command(host: str = "127.0.0.1") -> list[str]:
    return [
        "uv",
        "run",
        "python",
        "-m",
        "uvicorn",
        "splat_replay.bootstrap.web_app:app",
        "--factory",
        "--host",
        host,
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
    *,
    remote_access_enabled: bool = False,
) -> tuple[DevLaunchSpec, ...]:
    network = resolve_dev_server_network(remote_access_enabled)
    return (
        DevLaunchSpec(
            title="Splat Replay Frontend Dev",
            working_dir=repo_root / "frontend",
            command=_build_frontend_dev_command(
                windows=True,
                host=network.frontend_host,
            ),
        ),
        DevLaunchSpec(
            title="Splat Replay Backend Dev",
            working_dir=repo_root / "backend",
            command=_build_backend_dev_command(network.backend_host),
        ),
    )


def launch_windows_dev_servers(
    repo_root: Path,
    *,
    remote_access_enabled: bool = False,
) -> None:
    network = resolve_dev_server_network(remote_access_enabled)
    _apply_backend_dev_environment(network)
    for spec in build_windows_dev_launch_specs(
        repo_root,
        remote_access_enabled=remote_access_enabled,
    ):
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


def _start_inline_dev_servers(
    frontend_dir: Path,
    backend_dir: Path,
    *,
    windows: bool,
    network: DevServerNetwork,
) -> None:
    """同一ターミナル内でフロント・バックエンドを起動し、Ctrl+C で一括停止する。"""
    print("フロントエンド開発サーバーを起動中...")
    try:
        frontend_process = subprocess.Popen(
            _build_frontend_dev_command(
                windows=windows,
                host=network.frontend_host,
            ),
            cwd=frontend_dir,
        )
    except Exception as error:
        print(f"エラー: フロントエンドサーバーの起動に失敗しました: {error}")
        sys.exit(1)

    time.sleep(2)

    print("バックエンドサーバーを起動中...")
    try:
        backend_process = subprocess.Popen(
            _build_backend_dev_command(network.backend_host),
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


def _remote_access_enabled() -> bool:
    from splat_replay.infrastructure.config import load_settings_from_toml

    return load_settings_from_toml().remote_access.enabled


def _apply_backend_dev_environment(network: DevServerNetwork) -> None:
    os.environ["SPLAT_REPLAY_BACKEND_BIND_HOST"] = network.backend_host
    os.environ["SPLAT_REPLAY_BACKEND_PORT"] = str(network.backend_port)
    os.environ["SPLAT_REPLAY_FRONTEND_PORT"] = str(network.frontend_port)


def _port_accepts_connection(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def _is_dev_port_in_use(port: int) -> bool:
    return _port_accepts_connection(
        "127.0.0.1", port
    ) or _port_accepts_connection("::1", port)


def _find_occupied_dev_ports() -> tuple[int, ...]:
    return tuple(port for port in (5173, 8000) if _is_dev_port_in_use(port))


def _ensure_dev_ports_available() -> None:
    occupied_ports = _find_occupied_dev_ports()
    if not occupied_ports:
        return

    ports = ", ".join(str(port) for port in occupied_ports)
    print(
        f"エラー: 開発サーバー用ポートが既に使用中です: {ports}",
        file=sys.stderr,
    )
    print(
        "既存の task dev / frontend / backend ウィンドウを停止してから再実行してください。",
        file=sys.stderr,
    )
    sys.exit(1)


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
    _ensure_dev_ports_available()

    network = resolve_dev_server_network(_remote_access_enabled())
    _apply_backend_dev_environment(network)

    _start_inline_dev_servers(
        frontend_dir,
        backend_dir,
        windows=(os.name == "nt"),
        network=network,
    )


if __name__ == "__main__":
    start_dev_server()
