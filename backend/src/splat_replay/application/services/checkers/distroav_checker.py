"""OBS に読み込まれる候補パスの DistroAV / obs-ndi 実体を検査する。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from splat_replay.application.interfaces import (
    EnvironmentPort,
    FileSystemPort,
    LoggerPort,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)
from splat_replay.application.services.system.software_checker import (
    SoftwareChecker,
)


class DistroAVChecker:
    """保存済み OBS が検索する既知候補に plugin binary があるか調べる。

    ファイル存在だけを確認し、OBS が実際に plugin をロードしたことは保証しない。
    """

    def __init__(
        self,
        logger: LoggerPort,
        file_system: FileSystemPort,
        obs_checker: SoftwareChecker,
        environment: EnvironmentPort,
    ) -> None:
        self._logger = logger
        self._file_system = file_system
        self._obs_checker = obs_checker
        self._environment = environment

    def check(self) -> SoftwareCheckResult:
        """OBS を起動せず、既知の plugin binary 配置だけを確認する。"""
        obs_result = self._obs_checker.check()
        obs_executable = obs_result.installation_path
        if not obs_result.is_installed or obs_executable is None:
            return SoftwareCheckResult(is_installed=False)

        if sys.platform == "darwin":
            candidates = self._macos_candidates(obs_executable)
        elif sys.platform == "win32":
            candidates = self._windows_candidates(obs_executable)
        else:
            candidates = []
        candidates.extend(self._custom_plugin_path_candidates(obs_executable))

        for path in candidates:
            if self._file_system.is_file(path):
                self._logger.info("OBS NDI plugin binary found")
                return SoftwareCheckResult(
                    is_installed=True,
                    installation_path=path,
                )

        self._logger.info("OBS NDI plugin binary not found")
        return SoftwareCheckResult(
            is_installed=False,
            error_message="OBS の NDI プラグイン実行ファイルが見つかりませんでした",
        )

    def _macos_candidates(self, obs_executable: Path) -> list[Path]:
        candidates = [
            Path.home()
            / "Library/Application Support/obs-studio/plugins/distroav.plugin/Contents/MacOS/distroav",
            Path(
                "/Library/Application Support/obs-studio/plugins/distroav.plugin/Contents/MacOS/distroav"
            ),
            # 既存 obs-ndi は移行成功の判定ではなく、互換候補として検査する。
            Path.home()
            / "Library/Application Support/obs-studio/plugins/obs-ndi.plugin/Contents/MacOS/obs-ndi",
            Path(
                "/Library/Application Support/obs-studio/plugins/obs-ndi.plugin/Contents/MacOS/obs-ndi"
            ),
        ]
        app_bundle = next(
            (
                parent
                for parent in obs_executable.parents
                if parent.suffix.casefold() == ".app"
            ),
            None,
        )
        if app_bundle is not None:
            candidates.extend(
                (
                    app_bundle
                    / "Contents/PlugIns/distroav.plugin/Contents/MacOS/distroav",
                    app_bundle
                    / "Contents/PlugIns/obs-ndi.plugin/Contents/MacOS/obs-ndi",
                )
            )
        return candidates

    def _windows_candidates(self, obs_executable: Path) -> list[Path]:
        obs_root = self._windows_install_root(obs_executable)
        if obs_root is None:
            return []

        candidates = [
            # OBS 33 以降のルート配置と、従来の配置。
            obs_root / "plugins/distroav/distroav.dll",
            obs_root / "plugins/obs-ndi/obs-ndi.dll",
            obs_root / "obs-plugins/64bit/distroav.dll",
            obs_root / "obs-plugins/64bit/obs-ndi.dll",
            # OBS インストーラーがカスタム配置先として使う data/plugins。
            obs_root / "data/plugins/distroav/distroav.dll",
            obs_root / "data/plugins/obs-ndi/obs-ndi.dll",
            obs_root / "data/plugins/distroav/bin/64bit/distroav.dll",
            obs_root / "data/plugins/obs-ndi/bin/64bit/obs-ndi.dll",
        ]
        program_data = self._environment.get("PROGRAMDATA")
        if program_data:
            plugin_root = Path(program_data) / "obs-studio/plugins"
            candidates.extend(
                (
                    # OBS 33 以降の現行モジュール形式。
                    plugin_root / "distroav/distroav.dll",
                    plugin_root / "obs-ndi/obs-ndi.dll",
                    # OBS の従来モジュール形式。
                    plugin_root / "distroav/bin/64bit/distroav.dll",
                    plugin_root / "obs-ndi/bin/64bit/obs-ndi.dll",
                )
            )
        return candidates

    def _custom_plugin_path_candidates(
        self, obs_executable: Path
    ) -> list[Path]:
        raw_paths = self._environment.get("OBS_PLUGINS_PATH")
        if not raw_paths:
            return []

        candidates: list[Path] = []
        for raw_path in raw_paths.split(os.pathsep):
            if not raw_path.strip():
                continue
            plugin_root = Path(raw_path.strip())
            if not plugin_root.is_absolute():
                if sys.platform == "darwin":
                    # LaunchServices の相対パス基準はこの起動方法では特定できない。
                    continue
                # ProcessManager は OBS の実行ファイルの親ディレクトリを作業場所にする。
                plugin_root = obs_executable.parent / plugin_root
            if sys.platform == "darwin":
                candidates.extend(
                    (
                        plugin_root
                        / "distroav.plugin/Contents/MacOS/distroav",
                        plugin_root / "obs-ndi.plugin/Contents/MacOS/obs-ndi",
                    )
                )
            else:
                candidates.extend(
                    (
                        plugin_root / "distroav.dll",
                        plugin_root / "distroav/distroav.dll",
                        plugin_root / "distroav/bin/64bit/distroav.dll",
                        plugin_root / "obs-ndi/obs-ndi.dll",
                        plugin_root / "obs-ndi/bin/64bit/obs-ndi.dll",
                    )
                )
        return candidates

    @staticmethod
    def _windows_install_root(obs_executable: Path) -> Path | None:
        parents = obs_executable.parents
        if (
            len(parents) < 3
            or parents[0].name.casefold() != "64bit"
            or parents[1].name.casefold() != "bin"
        ):
            return None
        return parents[2]
