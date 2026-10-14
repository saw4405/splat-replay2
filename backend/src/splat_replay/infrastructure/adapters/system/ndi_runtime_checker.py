"""OS にインストールされた NDI Runtime を確認する adapter。"""

from __future__ import annotations

import ctypes
import re
import sys
from pathlib import Path

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import FileSystemPort
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)


class NDIRuntimeChecker:
    """OS にインストールされた NDI Runtime を確認する。"""

    _MACOS_RUNTIME_PATH = Path("/usr/local/lib/libndi.dylib")
    _MINIMUM_MACOS_VERSION = (6, 3)

    def __init__(
        self, logger: BoundLogger, file_system: FileSystemPort
    ) -> None:
        self._logger = logger
        self._file_system = file_system

    def check(self) -> SoftwareCheckResult:
        if sys.platform != "darwin":
            return self._check_windows_runtime()

        runtime_path = self._MACOS_RUNTIME_PATH
        if not self._file_system.is_file(runtime_path):
            return SoftwareCheckResult(
                is_installed=False,
                error_message="NDI Runtime が見つかりませんでした",
            )

        try:
            runtime = ctypes.CDLL(str(runtime_path))
            get_version = ctypes.CFUNCTYPE(ctypes.c_char_p)(
                ("NDIlib_version", runtime)
            )
            raw_version = get_version()
        except Exception as exc:
            self._logger.warning(
                "NDI Runtime version lookup failed", error=str(exc)
            )
            return SoftwareCheckResult(
                is_installed=False,
                installation_path=runtime_path,
                error_message="NDI Runtime のバージョンを確認できませんでした",
            )

        if not isinstance(raw_version, bytes):
            return SoftwareCheckResult(
                is_installed=False,
                installation_path=runtime_path,
                error_message="NDI Runtime のバージョンを確認できませんでした",
            )

        version_matches = re.findall(
            rb"(?<!\d)(\d+\.\d+(?:\.\d+){0,2})", raw_version
        )
        if not version_matches:
            return SoftwareCheckResult(
                is_installed=False,
                installation_path=runtime_path,
                error_message="NDI Runtime のバージョンを確認できませんでした",
            )

        version = version_matches[-1].decode("ascii")
        version_parts = tuple(int(part) for part in version.split("."))
        if version_parts[:2] < self._MINIMUM_MACOS_VERSION:
            return SoftwareCheckResult(
                is_installed=False,
                version=version,
                installation_path=runtime_path,
                error_message=(
                    "DistroAV 6.2.1 には NDI Runtime 6.3 以降が必要です "
                    f"(検出: {version})"
                ),
            )

        return SoftwareCheckResult(
            is_installed=True,
            version=version,
            installation_path=runtime_path,
        )

    def _check_windows_runtime(self) -> SoftwareCheckResult:
        common_paths = [
            Path("C:/Program Files/NDI/NDI 6 Runtime/v6"),
            Path("C:/Program Files/NDI/NDI 5 Runtime/v5"),
            Path("C:/Program Files (x86)/NDI/NDI 6 Runtime/v6"),
            Path("C:/Program Files (x86)/NDI/NDI 5 Runtime/v5"),
        ]
        for path in common_paths:
            dll_path = path / "Processing.NDI.Lib.x64.dll"
            if self._file_system.is_dir(path) and self._file_system.exists(
                dll_path
            ):
                version = "6.x" if "NDI 6" in str(path) else "5.x"
                return SoftwareCheckResult(
                    is_installed=True,
                    version=version,
                    installation_path=path,
                )
        return SoftwareCheckResult(
            is_installed=False,
            error_message="NDI Runtime が見つかりませんでした",
        )
