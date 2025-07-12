from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))  # noqa: E402

from typer.testing import CliRunner  # noqa: E402
from splat_replay.cli import app, container  # noqa: E402


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = result.output
    assert "Splat Replay" in output
    assert "auto" in output
    assert "upload" in output


def test_auto(monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        from splat_replay.application.use_cases.auto import AutoUseCase
        from splat_replay.domain.services.state_machine import (
            StateMachine,
            Event,
        )

        async def _execute(self, timeout=None):
            sm = container.resolve(StateMachine)
            sm.handle(Event.DEVICE_CONNECTED)
            sm.handle(Event.INITIALIZED)
            return None

        monkeypatch.setattr(AutoUseCase, "execute", _execute)

        result = runner.invoke(app, ["auto"])
    assert result.exit_code == 0
