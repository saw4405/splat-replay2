from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))  # noqa: E402

from typer.testing import CliRunner  # noqa: E402
from splat_replay import cli  # noqa: E402
from splat_replay.cli import app  # noqa: E402


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = result.output
    assert "Splat Replay" in output
    assert "init" in output
    assert "auto" in output
    assert "pause" in output
    assert "resume" in output
    assert "stop" in output


def test_record_without_init(monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        from splat_replay.application.use_cases.record_battle import (
            RecordBattleUseCase,
        )

        monkeypatch.setattr(RecordBattleUseCase, "execute", lambda self: None)

        class DummyCheck:
            def execute(self) -> bool:
                return True

        original_resolve = cli.resolve

        def fake_resolve(cls):
            if cls is cli.CheckInitializationUseCase:
                return DummyCheck()
            return original_resolve(cls)

        monkeypatch.setattr(cli, "resolve", fake_resolve)
        result = runner.invoke(app, ["record"])
    assert result.exit_code == 0
