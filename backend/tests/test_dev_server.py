from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TypedDict

import pytest

from splat_replay.bootstrap.dev_server import (
    build_windows_dev_launch_specs,
    launch_windows_dev_servers,
)


class PopenCall(TypedDict):
    args: list[str]
    creationflags: int


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
