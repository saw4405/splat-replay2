from __future__ import annotations

from pathlib import Path
from typing import Optional, cast
from unittest.mock import MagicMock

import pytest

from splat_replay.application.interfaces import CommandResult, FileSystemPort
from splat_replay.application.services.checkers import (
    FFMPEGChecker,
    OBSChecker,
    TesseractChecker,
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


def test_windows_tesseract_path_fallback_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
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

    assert checker.check().is_installed is True


def test_macos_obs_checks_the_application_bundle_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    obs_executable = Path("/Applications/OBS.app/Contents/MacOS/OBS")
    checker = OBSChecker(
        MagicMock(), cast(FileSystemPort, FakeFileSystem({obs_executable}))
    )

    result = checker.check()

    assert result.is_installed is True
    assert result.installation_path == obs_executable
