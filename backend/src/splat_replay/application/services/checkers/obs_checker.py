"""OBS インストール状態チェッカー。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from splat_replay.application.interfaces import FileSystemPort, LoggerPort
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)


class OBSChecker:
    """OBS Studio のインストール状態を確認するチェッカー。"""

    def __init__(
        self, logger: LoggerPort, file_system: FileSystemPort
    ) -> None:
        """チェッカーを初期化する。

        Args:
            logger: ロガーポート
        """
        self._logger = logger
        self._file_system = file_system

    def check(self) -> SoftwareCheckResult:
        """OBSのインストール状態を確認する。

        Returns:
            OBSのチェック結果
        """
        self._logger.info("Checking OBS installation")

        # OBSの実行ファイルパスを確認
        common_paths = [
            Path("C:/Program Files/obs-studio/bin/64bit/obs64.exe"),
            Path("C:/Program Files (x86)/obs-studio/bin/64bit/obs64.exe"),
        ]

        for path in common_paths:
            if self._file_system.is_file(path):
                self._logger.info("OBS found", path=str(path))
                # バージョン情報を取得
                version = self._get_obs_version(path)
                return SoftwareCheckResult(
                    is_installed=True,
                    version=version,
                    installation_path=path,
                )

        self._logger.info("OBS not found")
        return SoftwareCheckResult(
            is_installed=False,
            error_message="OBS Studio が見つかりませんでした",
        )

    def _get_obs_version(self, obs_path: Path) -> Optional[str]:
        """OBSのバージョン情報を取得する。

        Args:
            obs_path: OBSの実行ファイルパス

        Returns:
            バージョン情報（取得できない場合はNone）
        """
        try:
            # OBSのバージョン情報はファイルプロパティから取得する必要がある
            # ここでは簡易的にNoneを返す（実装は後で拡張可能）
            return None
        except Exception as e:
            self._logger.warning(
                "Failed to get OBS version",
                error=str(e),
            )
            return None
