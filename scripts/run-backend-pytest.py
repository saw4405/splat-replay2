"""backend pytest を checkout 内の一時ディレクトリで実行する。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def main() -> int:
    """pytest を実行し、Taskfile と共通の終了規約を適用する。"""
    repo_root = Path(__file__).resolve().parents[1]
    temp_root = repo_root / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("UV_CACHE_DIR", str(repo_root / ".uv-cache"))
    os.environ.setdefault(
        "UV_PYTHON_INSTALL_DIR", str(repo_root / ".uv-python")
    )
    for variable in ("TMP", "TEMP", "TMPDIR"):
        os.environ[variable] = str(temp_root)

    base_temp = temp_root / f"pytest-basetemp-{os.getpid()}"
    exit_code = int(
        pytest.main(
            [
                f"--basetemp={base_temp}",
                "-p",
                "no:cacheprovider",
                *sys.argv[1:],
            ]
        )
    )
    if exit_code == 5 and os.getenv("PYTEST_ALLOW_NO_TESTS") == "1":
        return 0
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
