from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import MagicMock

import pytest

from splat_replay.application.interfaces import FileSystemPort
from splat_replay.infrastructure.adapters.system.ndi_runtime_checker import (
    NDIRuntimeChecker,
)


class FakeFileSystem:
    def __init__(
        self,
        *,
        existing_dir: Path | None = None,
        existing_file: Path | None = None,
    ) -> None:
        self.existing_dir = existing_dir
        self.existing_file = existing_file

    def is_dir(self, path: Path) -> bool:
        return path == self.existing_dir

    def is_file(self, path: Path) -> bool:
        return path == self.existing_file

    def exists(self, path: Path) -> bool:
        return path == (
            self.existing_dir / "Processing.NDI.Lib.x64.dll"
            if self.existing_dir is not None
            else None
        )


def patch_macos_runtime_version(
    monkeypatch: pytest.MonkeyPatch, raw_version: bytes | None
) -> None:
    monkeypatch.setattr(ctypes, "CDLL", lambda _path: object())

    def make_function_type(
        _restype: object,
    ) -> Callable[[tuple[str, object]], Callable[[], bytes | None]]:
        return lambda _symbol: lambda: raw_version

    monkeypatch.setattr(ctypes, "CFUNCTYPE", make_function_type)


def test_macos_does_not_accept_bundled_cyndilib_without_system_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finder_calls: list[str] = []

    class FakeFinder:
        def open(self) -> None:
            finder_calls.append("open")

        def close(self) -> None:
            finder_calls.append("close")

    package = ModuleType("cyndilib")
    package.__path__ = []  # type: ignore[attr-defined]
    finder_module = ModuleType("cyndilib.finder")
    setattr(finder_module, "Finder", FakeFinder)
    monkeypatch.setitem(sys.modules, "cyndilib", package)
    monkeypatch.setitem(sys.modules, "cyndilib.finder", finder_module)
    monkeypatch.setattr("sys.platform", "darwin")

    result = NDIRuntimeChecker(
        MagicMock(), cast(FileSystemPort, FakeFileSystem())
    ).check()

    assert result.is_installed is False
    assert result.error_message == "NDI Runtime が見つかりませんでした"
    assert finder_calls == []


@pytest.mark.parametrize(
    ("raw_version", "expected_installed", "expected_version"),
    [
        (b"NDI SDK APPLE 09:05:57 May 6 2024 6.3.2.0", True, "6.3.2.0"),
        (b"NDI SDK APPLE 6.2.9.0", False, "6.2.9.0"),
        (b"NDI SDK APPLE unknown", False, None),
        (None, False, None),
    ],
)
def test_macos_runtime_requires_a_known_version_at_least_6_3(
    monkeypatch: pytest.MonkeyPatch,
    raw_version: bytes | None,
    expected_installed: bool,
    expected_version: str | None,
) -> None:
    runtime_path = Path("/usr/local/lib/libndi.dylib")
    monkeypatch.setattr("sys.platform", "darwin")
    patch_macos_runtime_version(monkeypatch, raw_version)

    result = NDIRuntimeChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem(existing_file=runtime_path)),
    ).check()

    assert result.is_installed is expected_installed
    assert result.version == expected_version
    assert result.installation_path == runtime_path


def test_macos_runtime_load_failure_is_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_path = Path("/usr/local/lib/libndi.dylib")
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(
        ctypes, "CDLL", MagicMock(side_effect=OSError("cannot load dylib"))
    )

    result = NDIRuntimeChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem(existing_file=runtime_path)),
    ).check()

    assert result.is_installed is False
    assert result.version is None
    assert result.installation_path == runtime_path


def test_windows_ndi_path_check_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    ndi_dir = Path("C:/Program Files/NDI/NDI 6 Runtime/v6")

    result = NDIRuntimeChecker(
        MagicMock(),
        cast(FileSystemPort, FakeFileSystem(existing_dir=ndi_dir)),
    ).check()

    assert result.is_installed is True
    assert result.version == "6.x"
    assert result.installation_path == ndi_dir
