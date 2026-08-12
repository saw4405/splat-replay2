from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy-desktop.ps1"


def _write_fake_git(bin_dir: Path) -> None:
    git_cmd = bin_dir / "git.cmd"
    git_cmd.write_text(
        "\r\n".join(
            [
                "@echo off",
                "setlocal",
                'if "%~1"=="-C" (',
                "  shift",
                "  shift",
                ")",
                'if "%~1"=="-c" (',
                '  if not "%~2"=="core.quotePath=false" (',
                "    >&2 echo unexpected git config: %~2",
                "    exit /b 2",
                "  )",
                "  shift",
                "  shift",
                ")",
                'if "%~1"=="rev-parse" (',
                "  echo 0123456789abcdef0123456789abcdef01234567",
                "  exit /b 0",
                ")",
                'if "%~1"=="--no-pager" (',
                "  >&2 echo warning: in the working copy of "
                "'backend/src/splat_replay/application/use_cases/assets/"
                "list_edited_videos.py', CRLF will be replaced by LF the next "
                "time Git touches it",
                "  echo diff --git a/example.py b/example.py",
                "  exit /b 0",
                ")",
                'if "%~1"=="ls-files" (',
                "  exit /b 0",
                ")",
                ">&2 echo unexpected git args: %*",
                "exit /b 2",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _parse_result_json(stdout: str) -> dict[str, Any]:
    for line in stdout.splitlines():
        if line.startswith("RESULT_JSON: "):
            payload = line.removeprefix("RESULT_JSON: ")
            return json.loads(payload)
    raise AssertionError(f"RESULT_JSON line was not found: {stdout}")


def _powershell_literal(value: Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_inspect_with_code_page(
    *,
    repo_root: Path,
    env_file: Path,
    code_page: int,
) -> subprocess.CompletedProcess[str]:
    command = (
        "[Console]::OutputEncoding = "
        f"[System.Text.Encoding]::GetEncoding({code_page}); "
        f"& {_powershell_literal(DEPLOY_SCRIPT)} "
        f"-Mode Inspect -RepoRoot {_powershell_literal(repo_root)} "
        f"-EnvFile {_powershell_literal(env_file)}; "
        "exit $LASTEXITCODE"
    )
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )


def test_deploy_inspect_ignores_git_crlf_warning_on_stderr(
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        pytest.skip(
            "deploy-desktop.ps1 is exercised through Windows PowerShell"
        )
    if shutil.which("powershell") is None:
        pytest.skip("PowerShell is required for deploy-desktop.ps1")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_git(fake_bin)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    deploy_dir = tmp_path / "desktop" / "SplatReplay"
    deploy_dir.mkdir(parents=True)
    env_file = repo_root / "deploy.env"
    env_file.write_text(
        f"SPLAT_REPLAY_DESKTOP_DEPLOY_DIR={deploy_dir}\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(DEPLOY_SCRIPT),
            "-Mode",
            "Inspect",
            "-RepoRoot",
            str(repo_root),
            "-EnvFile",
            str(env_file),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )

    result = _parse_result_json(completed.stdout)

    assert completed.returncode == 0, completed.stderr
    assert result["success"] is True
    assert "error" not in result


def test_deploy_inspect_accepts_untracked_unicode_path(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip(
            "deploy-desktop.ps1 is exercised through Windows PowerShell"
        )
    if shutil.which("powershell") is None:
        pytest.skip("PowerShell is required for deploy-desktop.ps1")

    git = shutil.which("git")
    if git is None:
        pytest.skip("Git is required for the unicode path regression test")
    assert git is not None

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(
        [git, "init", str(repo_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    (repo_root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(
        [git, "-C", str(repo_root), "add", "tracked.txt"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            git,
            "-C",
            str(repo_root),
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "initial",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    (repo_root / "設定.md").write_text("untracked\n", encoding="utf-8")

    deploy_dir = tmp_path / "desktop" / "SplatReplay"
    deploy_dir.mkdir(parents=True)
    env_file = repo_root / "deploy.env"
    env_file.write_text(
        f"SPLAT_REPLAY_DESKTOP_DEPLOY_DIR={deploy_dir}\n",
        encoding="utf-8",
    )

    completed_by_code_page = [
        _run_inspect_with_code_page(
            repo_root=repo_root,
            env_file=env_file,
            code_page=code_page,
        )
        for code_page in (65001, 932)
    ]
    results = [
        _parse_result_json(completed.stdout)
        for completed in completed_by_code_page
    ]

    for completed, result in zip(completed_by_code_page, results, strict=True):
        assert completed.returncode == 0, completed.stderr
        assert result["success"] is True
        assert "error" not in result
    assert len({result["fingerprint"] for result in results}) == 1
