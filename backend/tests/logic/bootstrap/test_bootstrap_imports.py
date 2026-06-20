from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_import_web_app_with_deprecation_as_error_succeeds() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_root / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error::DeprecationWarning",
            "-c",
            "from splat_replay.bootstrap.web_app import create_app; assert create_app",
        ],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
