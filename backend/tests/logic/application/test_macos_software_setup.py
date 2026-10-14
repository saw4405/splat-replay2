from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, cast
from unittest.mock import MagicMock

import pytest

from splat_replay.application.interfaces import (
    CommandExecutionError,
    CommandResult,
    FileSystemPort,
    SoftwareInstallAttempt,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
    SystemCheckService,
)
from splat_replay.application.services.setup.system_setup_service import (
    SystemSetupService,
)
from splat_replay.application.services.checkers import FLACChecker
from splat_replay.infrastructure.adapters.system.homebrew_software_installer import (
    HomebrewSoftwareInstaller,
)


class FakeCommandPort:
    def __init__(
        self,
        *,
        available: set[str] | None = None,
        results: dict[tuple[str, ...], CommandResult] | None = None,
    ) -> None:
        self.available = available or set()
        self.results = results or {}
        self.executed: list[tuple[str, ...]] = []
        self.timeouts: list[Optional[float]] = []

    def check_command_exists(self, command: str) -> bool:
        return command in self.available

    def execute_command(
        self, command: list[str], timeout: Optional[float] = None
    ) -> CommandResult:
        args = tuple(command)
        self.executed.append(args)
        self.timeouts.append(timeout)
        return self.results.get(args, CommandResult(0, "", ""))


class FakeFileSystem:
    def is_file(self, path: Path) -> bool:
        return False


class FakeEnvironment:
    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return default

    def set(self, name: str, value: str) -> None:
        pass


class FakeChecks:
    def __init__(
        self,
        *,
        ffmpeg: list[SoftwareCheckResult] | None = None,
        tesseract: list[SoftwareCheckResult] | None = None,
        flac: list[SoftwareCheckResult] | None = None,
    ) -> None:
        self.ffmpeg = ffmpeg or []
        self.tesseract = tesseract or []
        self.flac = flac or []
        self.ffmpeg_calls = 0
        self.tesseract_calls = 0
        self.flac_calls = 0

    def check_ffmpeg_installation(self) -> SoftwareCheckResult:
        self.ffmpeg_calls += 1
        return self.ffmpeg.pop(0)

    def check_tesseract_installation(self) -> SoftwareCheckResult:
        self.tesseract_calls += 1
        return self.tesseract.pop(0)

    def check_flac_installation(self) -> SoftwareCheckResult:
        self.flac_calls += 1
        return self.flac.pop(0)


class FakeInstaller:
    def __init__(self, attempt: SoftwareInstallAttempt) -> None:
        self.attempt = attempt
        self.software: list[Literal["ffmpeg", "tesseract", "flac"]] = []

    def install(
        self, software: Literal["ffmpeg", "tesseract", "flac"]
    ) -> SoftwareInstallAttempt:
        self.software.append(software)
        return self.attempt


def test_homebrew_missing_opens_terminal_and_chains_formula_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    commands = FakeCommandPort()
    installer = HomebrewSoftwareInstaller(commands, MagicMock())

    result = installer.install("tesseract")

    assert result.completed is False
    assert "Terminal" in (result.error_message or "")
    assert len(commands.executed) == 1
    assert commands.executed[0][:3] == ("/usr/bin/open", "-a", "Terminal")
    script_path = Path(commands.executed[0][3])
    try:
        script = script_path.read_text(encoding="utf-8")
        assert (
            "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
            in script
        )
        assert '/bin/bash -c "$(/usr/bin/curl -fsSL ' in script
        assert '&& eval "$(/opt/homebrew/bin/brew shellenv)"' in script
        assert (
            "&& /opt/homebrew/bin/brew install tesseract tesseract-lang"
            in script
        )
        assert "trap 'rm -f \"$script_path\"' EXIT" in script
    finally:
        script_path.unlink(missing_ok=True)


def test_existing_homebrew_install_failure_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    commands = FakeCommandPort(
        available={"brew"},
        results={
            ("brew", "install", "ffmpeg"): CommandResult(
                1, "", "download failed"
            )
        },
    )
    installer = HomebrewSoftwareInstaller(commands, MagicMock())

    result = installer.install("ffmpeg")

    assert result.completed is False
    assert result.error_message == "download failed"
    assert commands.executed == [("brew", "install", "ffmpeg")]


def test_terminal_open_failure_removes_temporary_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")

    class OpenFailureCommandPort(FakeCommandPort):
        def __init__(self) -> None:
            super().__init__()
            self.temp_path: Path | None = None

        def execute_command(
            self, command: list[str], timeout: Optional[float] = None
        ) -> CommandResult:
            args = tuple(command)
            self.executed.append(args)
            self.timeouts.append(timeout)
            self.temp_path = Path(args[-1])
            return CommandResult(1, "", "Terminal unavailable")

    commands = OpenFailureCommandPort()
    result = HomebrewSoftwareInstaller(commands, MagicMock()).install("ffmpeg")

    assert result.completed is False
    assert "Terminal を起動できませんでした" in (result.error_message or "")
    assert commands.executed[0][:3] == ("/usr/bin/open", "-a", "Terminal")
    assert commands.temp_path is not None
    assert not commands.temp_path.exists()


def test_existing_homebrew_uses_the_fixed_tesseract_formulae(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    commands = FakeCommandPort(available={"brew"})
    installer = HomebrewSoftwareInstaller(commands, MagicMock())

    result = installer.install("tesseract")

    assert result.completed is True
    assert commands.executed == [
        ("brew", "install", "tesseract", "tesseract-lang")
    ]
    assert commands.timeouts == [30 * 60]


def test_existing_homebrew_uses_fixed_flac_formula(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    commands = FakeCommandPort(available={"brew"})
    result = HomebrewSoftwareInstaller(commands, MagicMock()).install("flac")

    assert result.completed is True
    assert commands.executed == [("brew", "install", "flac")]


def test_homebrew_timeout_is_reported_as_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")

    class TimedOutCommandPort(FakeCommandPort):
        def execute_command(
            self, command: list[str], timeout: Optional[float] = None
        ) -> CommandResult:
            self.executed.append(tuple(command))
            self.timeouts.append(timeout)
            raise CommandExecutionError(
                "Command timed out after 1800 seconds", command
            )

    commands = TimedOutCommandPort(available={"brew"})
    result = HomebrewSoftwareInstaller(commands, MagicMock()).install("ffmpeg")

    assert result.completed is False
    assert "timed out" in (result.error_message or "")
    assert commands.executed == [("brew", "install", "ffmpeg")]
    assert commands.timeouts == [30 * 60]


def test_flac_checker_requires_a_runnable_path_command() -> None:
    commands = FakeCommandPort()
    checker = FLACChecker(commands, MagicMock())

    result = checker.check()

    assert result.is_installed is False
    assert "PATH" in (result.error_message or "")
    assert commands.executed == []


def test_flac_checker_verifies_the_command_and_reports_version() -> None:
    commands = FakeCommandPort(
        available={"flac"},
        results={("flac", "--version"): CommandResult(0, "flac 1.4.3\n", "")},
    )
    checker = FLACChecker(commands, MagicMock())

    result = checker.check()

    assert result.is_installed is True
    assert result.version == "flac 1.4.3"
    assert commands.executed == [("flac", "--version")]


def test_mac_setup_rechecks_after_completed_brew_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    checks = FakeChecks(
        ffmpeg=[
            SoftwareCheckResult(is_installed=False),
            SoftwareCheckResult(is_installed=True, version="7.1"),
        ]
    )
    installer = FakeInstaller(SoftwareInstallAttempt(completed=True))
    service = SystemSetupService(
        FakeCommandPort(),
        cast(FileSystemPort, FakeFileSystem()),
        FakeEnvironment(),
        MagicMock(),
        installer,
        cast(SystemCheckService, checks),
    )

    result = service.setup_ffmpeg()

    assert result.is_installed is True
    assert result.version == "7.1"
    assert checks.ffmpeg_calls == 2
    assert installer.software == ["ffmpeg"]


def test_mac_setup_reports_terminal_install_as_still_uninstalled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    checks = FakeChecks(ffmpeg=[SoftwareCheckResult(is_installed=False)])
    waiting_message = "Terminal で導入中です。完了後に再確認してください。"
    service = SystemSetupService(
        FakeCommandPort(),
        cast(FileSystemPort, FakeFileSystem()),
        FakeEnvironment(),
        MagicMock(),
        FakeInstaller(
            SoftwareInstallAttempt(
                completed=False, error_message=waiting_message
            )
        ),
        cast(SystemCheckService, checks),
    )

    result = service.setup_ffmpeg()

    assert result.is_installed is False
    assert result.error_message == waiting_message
    assert checks.ffmpeg_calls == 1


def test_mac_flac_setup_rechecks_and_only_completes_when_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    checks = FakeChecks(
        flac=[
            SoftwareCheckResult(is_installed=False),
            SoftwareCheckResult(is_installed=True, version="flac 1.4.3"),
        ]
    )
    installer = FakeInstaller(SoftwareInstallAttempt(completed=True))
    service = SystemSetupService(
        FakeCommandPort(),
        cast(FileSystemPort, FakeFileSystem()),
        FakeEnvironment(),
        MagicMock(),
        installer,
        cast(SystemCheckService, checks),
    )

    result = service.setup_flac()

    assert result.is_installed is True
    assert result.version == "flac 1.4.3"
    assert checks.flac_calls == 2
    assert installer.software == ["flac"]


def test_mac_flac_setup_stays_uninstalled_after_failed_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    checks = FakeChecks(flac=[SoftwareCheckResult(is_installed=False)])
    installer = FakeInstaller(
        SoftwareInstallAttempt(completed=False, error_message="brew failed")
    )
    service = SystemSetupService(
        FakeCommandPort(),
        cast(FileSystemPort, FakeFileSystem()),
        FakeEnvironment(),
        MagicMock(),
        installer,
        cast(SystemCheckService, checks),
    )

    result = service.setup_flac()

    assert result.is_installed is False
    assert result.error_message == "brew failed"
    assert checks.flac_calls == 1


def test_mac_flac_setup_stays_uninstalled_when_post_install_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    checks = FakeChecks(
        flac=[
            SoftwareCheckResult(is_installed=False),
            SoftwareCheckResult(
                is_installed=False,
                error_message="FLAC の実行確認に失敗しました",
            ),
        ]
    )
    service = SystemSetupService(
        FakeCommandPort(),
        cast(FileSystemPort, FakeFileSystem()),
        FakeEnvironment(),
        MagicMock(),
        FakeInstaller(SoftwareInstallAttempt(completed=True)),
        cast(SystemCheckService, checks),
    )

    result = service.setup_flac()

    assert result.is_installed is False
    assert result.error_message == "FLAC の実行確認に失敗しました"
    assert checks.flac_calls == 2


def test_mac_setup_keeps_japanese_data_failure_uninstalled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    missing_jpn = SoftwareCheckResult(
        is_installed=False,
        error_message="日本語 OCR データ (jpn) が見つかりませんでした",
    )
    checks = FakeChecks(tesseract=[missing_jpn, missing_jpn])
    service = SystemSetupService(
        FakeCommandPort(),
        cast(FileSystemPort, FakeFileSystem()),
        FakeEnvironment(),
        MagicMock(),
        FakeInstaller(SoftwareInstallAttempt(completed=True)),
        cast(SystemCheckService, checks),
    )

    result = service.setup_tesseract()

    assert result.is_installed is False
    assert result.error_message == missing_jpn.error_message
    assert checks.tesseract_calls == 2


def test_windows_setup_keeps_existing_command_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    commands = FakeCommandPort(
        results={
            ("ffmpeg", "-version"): CommandResult(
                0, "ffmpeg version 7.1\n", ""
            )
        }
    )
    installer = FakeInstaller(SoftwareInstallAttempt(completed=False))
    service = SystemSetupService(
        commands,
        cast(FileSystemPort, FakeFileSystem()),
        FakeEnvironment(),
        MagicMock(),
        installer,
        cast(SystemCheckService, FakeChecks()),
    )

    result = service.setup_ffmpeg()

    assert result.is_installed is True
    assert commands.executed == [("ffmpeg", "-version")]
    assert installer.software == []
