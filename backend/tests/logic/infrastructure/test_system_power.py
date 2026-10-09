from __future__ import annotations

import subprocess
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.infrastructure.adapters.system import system_power
from splat_replay.infrastructure.adapters.system.system_power import (
    SystemPower,
)


def _system_power() -> SystemPower:
    return SystemPower(cast(BoundLogger, Mock()))


@pytest.fixture(autouse=True)
def _windows_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_power.sys, "platform", "win32")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("platform", "expected_command"),
    [
        ("darwin", ("pmset", "sleepnow")),
        (
            "win32",
            ("rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"),
        ),
    ],
)
async def test_sleep_uses_platform_command(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    expected_command: tuple[str, ...],
) -> None:
    monkeypatch.setattr(system_power.sys, "platform", platform)
    process = Mock()
    process.wait = AsyncMock(return_value=0)
    create_process = AsyncMock(return_value=process)
    monkeypatch.setattr(
        system_power.asyncio, "create_subprocess_exec", create_process
    )

    await _system_power().sleep()

    assert create_process.call_args.args == expected_command


@pytest.mark.asyncio
async def test_sleep_rejects_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(system_power.sys, "platform", "linux")
    create_process = AsyncMock()
    monkeypatch.setattr(
        system_power.asyncio, "create_subprocess_exec", create_process
    )

    with pytest.raises(RuntimeError, match="linux"):
        await _system_power().sleep()

    create_process.assert_not_awaited()


@pytest.mark.asyncio
async def test_sleep_async_process_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = Mock()
    process.wait = AsyncMock(return_value=0)
    monkeypatch.setattr(
        system_power.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=process),
    )

    await _system_power().sleep()


@pytest.mark.asyncio
async def test_sleep_async_process_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = Mock()
    process.wait = AsyncMock(return_value=1)
    monkeypatch.setattr(
        system_power.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=process),
    )

    with pytest.raises(subprocess.CalledProcessError) as error:
        await _system_power().sleep()

    assert error.value.returncode == 1


@pytest.mark.asyncio
async def test_sleep_async_launch_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        system_power.asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=FileNotFoundError("rundll32.exe")),
    )

    with pytest.raises(FileNotFoundError):
        await _system_power().sleep()


@pytest.mark.asyncio
async def test_sleep_fallback_process_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        system_power.asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=NotImplementedError),
    )
    run = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(system_power.subprocess, "run", run)

    await _system_power().sleep()

    assert run.call_args.kwargs["check"] is True


@pytest.mark.asyncio
async def test_sleep_fallback_process_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        system_power.asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=NotImplementedError),
    )
    run = Mock(side_effect=subprocess.CalledProcessError(1, "rundll32.exe"))
    monkeypatch.setattr(system_power.subprocess, "run", run)

    with pytest.raises(subprocess.CalledProcessError) as error:
        await _system_power().sleep()

    assert error.value.returncode == 1
    assert run.call_args.kwargs["check"] is True


@pytest.mark.asyncio
async def test_sleep_fallback_launch_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        system_power.asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=NotImplementedError),
    )
    monkeypatch.setattr(
        system_power.subprocess,
        "run",
        Mock(side_effect=FileNotFoundError("rundll32.exe")),
    )

    with pytest.raises(FileNotFoundError):
        await _system_power().sleep()
