from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TypedDict

import pytest

from splat_replay.bootstrap.dev_server import (
    build_windows_dev_launch_specs,
    launch_windows_dev_servers,
    start_dev_server,
)


class PopenCall(TypedDict):
    args: list[str]
    creationflags: int


class InlinePopenCall(TypedDict):
    args: list[str]
    cwd: Path


def test_build_windows_dev_launch_specs_include_reload() -> None:
    repo_root = Path("C:/work/splat-replay2")

    frontend_spec, backend_spec = build_windows_dev_launch_specs(repo_root)

    assert frontend_spec.title == "Splat Replay Frontend Dev"
    assert frontend_spec.working_dir == repo_root / "frontend"
    assert frontend_spec.command == ["npm.cmd", "run", "dev"]

    assert backend_spec.title == "Splat Replay Backend Dev"
    assert backend_spec.working_dir == repo_root / "backend"
    assert backend_spec.command == [
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


def test_launch_windows_dev_servers_open_two_powershell_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    popen_calls: list[PopenCall] = []

    def fake_popen(
        args: list[str],
        *,
        creationflags: int,
    ) -> SimpleNamespace:
        popen_calls.append(
            {
                "args": args,
                "creationflags": creationflags,
            }
        )
        return SimpleNamespace()

    monkeypatch.setattr(
        "splat_replay.bootstrap.dev_server.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "splat_replay.bootstrap.dev_server.WINDOWS_NEW_CONSOLE",
        16,
    )

    launch_windows_dev_servers(Path("C:/work/splat-replay2"))

    assert len(popen_calls) == 2

    frontend_call, backend_call = popen_calls

    assert frontend_call["creationflags"] == 16
    assert frontend_call["args"][:3] == [
        "powershell.exe",
        "-NoLogo",
        "-NoExit",
    ]
    assert "Set-Location -LiteralPath 'C:/work/splat-replay2/frontend'" in str(
        frontend_call["args"][4]
    )
    assert "npm.cmd run dev" in str(frontend_call["args"][4])

    assert backend_call["creationflags"] == 16
    assert backend_call["args"][:3] == [
        "powershell.exe",
        "-NoLogo",
        "-NoExit",
    ]
    assert "Set-Location -LiteralPath 'C:/work/splat-replay2/backend'" in str(
        backend_call["args"][4]
    )
    assert "--reload" in str(backend_call["args"][4])


def test_start_dev_server_launches_inline_in_same_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """start_dev_server は同一ターミナル内で両プロセスを起動する。"""
    # ディレクトリ構成を用意
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "node_modules").mkdir()
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()

    monkeypatch.setattr(
        "splat_replay.bootstrap.dev_server._project_root",
        lambda: tmp_path,
    )

    popen_calls: list[InlinePopenCall] = []
    wait_called = 0
    interrupted = False

    class FakeProcess:
        def __init__(self, args: list[str], *, cwd: Path) -> None:
            popen_calls.append({"args": args, "cwd": cwd})

        def wait(self, timeout: float | None = None) -> None:
            nonlocal wait_called, interrupted
            wait_called += 1
            # 2つ目の wait で KeyboardInterrupt を1回だけ発生させて終了
            if wait_called >= 2 and not interrupted:
                interrupted = True
                raise KeyboardInterrupt

        def terminate(self) -> None:
            pass

        def kill(self) -> None:
            pass

    monkeypatch.setattr(
        "splat_replay.bootstrap.dev_server.subprocess.Popen",
        FakeProcess,
    )
    monkeypatch.setattr(
        "splat_replay.bootstrap.dev_server.time.sleep",
        lambda _: None,
    )

    start_dev_server()

    assert len(popen_calls) == 2

    frontend_call, backend_call = popen_calls

    # 同一プロセス内で起動（CREATE_NEW_CONSOLE なし）
    assert frontend_call["cwd"] == frontend_dir
    assert backend_call["cwd"] == backend_dir
    assert "--reload" in backend_call["args"]
