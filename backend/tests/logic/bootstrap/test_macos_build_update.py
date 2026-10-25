from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import psutil
import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.skipif(os.name == "nt", reason="macOS 用のシェル処理")
@pytest.mark.parametrize("running", [False, True])
def test_macos_build_refuses_to_replace_running_app(
    tmp_path: Path, running: bool
) -> None:
    taskfile = yaml.safe_load((REPO_ROOT / "Taskfile.yml").read_text())
    commands = taskfile["tasks"]["build:macos"]["cmds"]
    guard = next(
        entry["cmd"]
        for entry in commands
        if "cmd" in entry and "psutil.process_iter" in entry["cmd"]
    )
    assert isinstance(guard, str)
    executable = (
        tmp_path / "SplatReplay.app" / "Contents" / "MacOS" / "SplatReplay"
    )
    if running:
        executable.parent.mkdir(parents=True)
        # 実行中のテスト用 Python を、更新先アプリとして照合させる。
        executable.symlink_to(psutil.Process().exe())
    command = guard.replace("{{.VENV_PYTHON}}", sys.executable).replace(
        "{{.DIST_ROOT}}", str(tmp_path)
    )

    result = subprocess.run(
        ["/bin/sh", "-c", command], capture_output=True, text=True
    )

    assert result.returncode == (1 if running else 0), result.stderr
    if running:
        assert "終了してから再実行" in result.stderr
        assert executable.is_symlink()
