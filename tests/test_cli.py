from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))  # noqa: E402

from typer.testing import CliRunner  # noqa: E402
from splat_replay.cli import app  # noqa: E402


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Splat Replay" in result.output
