from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Optional, cast
from unittest.mock import MagicMock

import pytest

from splat_replay.application.interfaces import (
    CommandResult,
    FileSystemPort,
    OBSSettingsView,
    RequiredSetupConfigPort,
)
from splat_replay.application.services.checkers import (
    DistroAVChecker,
    FFMPEGChecker,
    OBSChecker,
    TesseractChecker,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)


class FakeCommandPort:
    def __init__(
        self,
        results: dict[tuple[str, ...], CommandResult],
        available: set[str] | None = None,
    ) -> None:
        self.results = results
        self.available = available or set()

    def check_command_exists(self, command: str) -> bool:
        return command in self.available

    def execute_command(
        self, command: list[str], timeout: Optional[float] = None
    ) -> CommandResult:
        return self.results.get(
            tuple(command), CommandResult(1, "", "not configured")
        )


class FakeFileSystem:
    def __init__(self, existing: set[Path] | None = None) -> None:
        self.existing = existing or set()

    def is_file(self, path: Path) -> bool:
        return path in self.existing


class FakeEnvironment:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    def get(self, name: str, default: str | None = None) -> str | None:
        return self.values.get(name, default)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value


class FakeRequiredSetupConfig:
    def __init__(self, executable_path: Path) -> None:
        self.executable_path = executable_path

    def get_obs_settings(self) -> OBSSettingsView:
        return cast(
            OBSSettingsView,
            SimpleNamespace(executable_path=self.executable_path),
        )


class FakeOBSChecker:
    def __init__(self, result: SoftwareCheckResult) -> None:
        self.result = result

    def check(self) -> SoftwareCheckResult:
        return self.result


def test_ffmpeg_requires_a_parseable_version() -> None:
    checker = FFMPEGChecker(
        FakeCommandPort(
            {
                ("ffmpeg", "-version"): CommandResult(
                    0, "unexpected output", ""
                )
            },
            {"ffmpeg"},
        ),
        MagicMock(),
    )

    assert checker.check().is_installed is False


@pytest.mark.parametrize(
    ("version_output", "language_output", "expected"),
    [
        (
            "tesseract 5.5.0\n",
            "List of available languages in /data/\neng\njpn\n",
            True,
        ),
        (
            "tesseract 5.5.0\n",
            "List of available languages in /data/\neng\njpn_vert\n",
            False,
        ),
        (
            "unknown\n",
            "List of available languages in /data/\neng\njpn\n",
            False,
        ),
    ],
)
def test_macos_tesseract_requires_exact_japanese_language(
    monkeypatch: pytest.MonkeyPatch,
    version_output: str,
    language_output: str,
    expected: bool,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    checker = TesseractChecker(
        FakeCommandPort(
            {
                ("tesseract", "--version"): CommandResult(
                    0, version_output, ""
                ),
                ("tesseract", "--list-langs"): CommandResult(
                    0, language_output, ""
                ),
            },
            {"tesseract"},
        ),
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem()),
    )

    assert checker.check().is_installed is expected


def test_macos_tesseract_does_not_use_the_windows_path_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    checker = TesseractChecker(
        FakeCommandPort({}, set()),
        MagicMock(),
        cast(
            FileSystemPort,
            FakeFileSystem(
                {Path("C:/Program Files/Tesseract-OCR/tesseract.exe")}
            ),
        ),
    )

    assert checker.check().is_installed is False


def test_windows_tesseract_path_fallback_accepts_default_english_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    executable = "C:/Program Files/Tesseract-OCR/tesseract.exe"
    checker = TesseractChecker(
        FakeCommandPort(
            {
                (executable, "--version"): CommandResult(
                    0, "tesseract 5.5.0\n", ""
                ),
                (executable, "--list-langs"): CommandResult(
                    0,
                    "List of available languages in ./tessdata/\neng\n",
                    "",
                ),
            },
            set(),
        ),
        MagicMock(),
        cast(
            FileSystemPort,
            FakeFileSystem({Path(executable)}),
        ),
    )

    assert checker.check().is_installed is True


def test_windows_tesseract_path_fallback_requires_default_english_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    executable = "C:/Program Files/Tesseract-OCR/tesseract.exe"
    checker = TesseractChecker(
        FakeCommandPort(
            {
                (executable, "--version"): CommandResult(
                    0, "tesseract 5.5.0\n", ""
                ),
                (executable, "--list-langs"): CommandResult(
                    0, "List of available languages in ./tessdata/\ndeu\n", ""
                ),
            },
            set(),
        ),
        MagicMock(),
        cast(
            FileSystemPort,
            FakeFileSystem({Path(executable)}),
        ),
    )

    assert checker.check().is_installed is False


def test_macos_obs_checks_the_application_bundle_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    obs_executable = Path("/Applications/OBS.app/Contents/MacOS/OBS")
    checker = OBSChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({obs_executable})),
        cast(
            RequiredSetupConfigPort,
            FakeRequiredSetupConfig(
                Path(r"C:\Program Files\obs-studio\bin\64bit\obs64.exe")
            ),
        ),
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == obs_executable


def test_obs_uses_saved_custom_path_without_falling_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    default_executable = Path("/Applications/OBS.app/Contents/MacOS/OBS")
    custom_executable = tmp_path / "OBS-custom.app/Contents/MacOS/OBS"
    checker = OBSChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({default_executable})),
        cast(
            RequiredSetupConfigPort,
            FakeRequiredSetupConfig(custom_executable),
        ),
    )

    result = checker.check()

    assert result.is_installed is False


def test_obs_uses_saved_custom_path_when_it_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    custom_executable = tmp_path / "OBS-custom.app/Contents/MacOS/OBS"
    checker = OBSChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({custom_executable})),
        cast(
            RequiredSetupConfigPort,
            FakeRequiredSetupConfig(custom_executable),
        ),
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == custom_executable


def test_obs_accepts_saved_windows_portable_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    executable = tmp_path / "portable/bin/64bit/obs64.exe"
    checker = OBSChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({executable})),
        cast(
            RequiredSetupConfigPort,
            FakeRequiredSetupConfig(executable),
        ),
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == executable


def test_obs_checker_reads_saved_executable_again_after_config_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    first_executable = tmp_path / "OBS-first.app/Contents/MacOS/OBS"
    updated_executable = tmp_path / "OBS-updated.app/Contents/MacOS/OBS"
    config = FakeRequiredSetupConfig(first_executable)
    checker = OBSChecker(
        MagicMock(),
        cast(
            FileSystemPort,
            FakeFileSystem({first_executable, updated_executable}),
        ),
        cast(RequiredSetupConfigPort, config),
    )

    first_result = checker.check()
    config.executable_path = updated_executable
    updated_result = checker.check()

    assert first_result.installation_path == first_executable
    assert updated_result.installation_path == updated_executable


def test_macos_distroav_checks_the_official_user_plugin_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    plugin = (
        tmp_path
        / "Library/Application Support/obs-studio/plugins/distroav.plugin/Contents/MacOS/distroav"
    )
    checker = DistroAVChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({plugin})),
        FakeOBSChecker(
            SoftwareCheckResult(
                is_installed=True,
                installation_path=Path(
                    "/Applications/OBS.app/Contents/MacOS/OBS"
                ),
            )
        ),
        FakeEnvironment(),
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == plugin


def test_windows_distroav_checks_the_official_programdata_plugin_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    program_data = tmp_path / "ProgramData"
    plugin = (
        program_data / "obs-studio/plugins/distroav/bin/64bit/distroav.dll"
    )
    checker = DistroAVChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({plugin})),
        FakeOBSChecker(
            SoftwareCheckResult(
                is_installed=True,
                installation_path=Path(
                    "C:/Program Files/obs-studio/bin/64bit/obs64.exe"
                ),
            )
        ),
        FakeEnvironment({"PROGRAMDATA": str(program_data)}),
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == plugin


def test_windows_distroav_checks_the_current_programdata_plugin_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    program_data = tmp_path / "ProgramData"
    plugin = program_data / "obs-studio/plugins/distroav/distroav.dll"
    checker = DistroAVChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({plugin})),
        FakeOBSChecker(
            SoftwareCheckResult(
                is_installed=True,
                installation_path=Path(
                    "C:/Program Files/obs-studio/bin/64bit/obs64.exe"
                ),
            )
        ),
        FakeEnvironment({"PROGRAMDATA": str(program_data)}),
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == plugin


def test_windows_distroav_checks_the_configured_portable_obs_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    executable = tmp_path / "portable/bin/64bit/obs64.exe"
    plugin = tmp_path / "portable/obs-plugins/64bit/distroav.dll"
    checker = DistroAVChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({plugin})),
        FakeOBSChecker(
            SoftwareCheckResult(
                is_installed=True, installation_path=executable
            )
        ),
        FakeEnvironment(),
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == plugin


def test_windows_distroav_checks_the_obs_33_portable_plugin_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    executable = tmp_path / "portable/bin/64bit/obs64.exe"
    plugin = tmp_path / "portable/plugins/distroav/distroav.dll"
    checker = DistroAVChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({plugin})),
        FakeOBSChecker(
            SoftwareCheckResult(
                is_installed=True, installation_path=executable
            )
        ),
        FakeEnvironment(),
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == plugin


def test_distroav_checks_the_configured_obs_plugin_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    executable = Path("/Applications/OBS.app/Contents/MacOS/OBS")
    plugin_root = tmp_path / "plugins"
    plugin = plugin_root / "distroav.plugin/Contents/MacOS/distroav"
    checker = DistroAVChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({plugin})),
        FakeOBSChecker(
            SoftwareCheckResult(
                is_installed=True, installation_path=executable
            )
        ),
        FakeEnvironment({"OBS_PLUGINS_PATH": str(plugin_root)}),
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == plugin


def test_macos_distroav_does_not_guess_relative_plugin_path_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    executable = tmp_path / "OBS.app/Contents/MacOS/OBS"
    guessed_plugin = (
        executable.parent
        / "relative-plugins/distroav.plugin/Contents/MacOS/distroav"
    )
    checker = DistroAVChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem({guessed_plugin})),
        FakeOBSChecker(
            SoftwareCheckResult(
                is_installed=True,
                installation_path=executable,
            )
        ),
        FakeEnvironment({"OBS_PLUGINS_PATH": "relative-plugins"}),
    )

    assert checker.check().is_installed is False
