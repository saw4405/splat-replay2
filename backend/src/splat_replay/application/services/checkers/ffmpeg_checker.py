"""FFMPEG インストール状態チェッカー。"""

from __future__ import annotations

import re
from typing import Optional

from splat_replay.application.interfaces import (
    CommandExecutionError,
    LoggerPort,
    SystemCommandPort,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)


class FFMPEGChecker:
    """FFMPEG のインストール状態を確認するチェッカー。"""

    def __init__(
        self,
        command_port: SystemCommandPort,
        logger: LoggerPort,
    ) -> None:
        """チェッカーを初期化する。

        Args:
            command_port: システムコマンド実行ポート
            logger: ロガーポート
        """
        self._command_port = command_port
        self._logger = logger

    def check(self) -> SoftwareCheckResult:
        """FFMPEGのインストール状態を確認する。

        Returns:
            FFMPEGのチェック結果
        """
        self._logger.info("Checking FFMPEG installation")

        # ffmpegコマンドが実行可能かチェック
        if not self._command_port.check_command_exists("ffmpeg"):
            self._logger.info("FFMPEG command not found")
            return SoftwareCheckResult(
                is_installed=False,
                error_message="FFMPEG が見つかりませんでした",
            )

        # バージョン情報を取得
        try:
            result = self._command_port.execute_command(
                ["ffmpeg", "-version"],
                timeout=5.0,
            )

            if result.success:
                version = self._extract_ffmpeg_version(result.stdout)
                self._logger.info("FFMPEG found", version=version)
                return SoftwareCheckResult(
                    is_installed=True,
                    version=version,
                )
            else:
                self._logger.warning(
                    "FFMPEG version check failed",
                    stderr=result.stderr,
                )
                return SoftwareCheckResult(
                    is_installed=False,
                    error_message="FFMPEG のバージョン確認に失敗しました",
                )

        except CommandExecutionError as e:
            self._logger.error(
                "FFMPEG version check error",
                error=str(e),
            )
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"FFMPEG の確認中にエラーが発生しました: {e}",
            )

    def _extract_ffmpeg_version(self, output: str) -> Optional[str]:
        """FFMPEGの出力からバージョン情報を抽出する。

        Args:
            output: ffmpeg -versionの出力

        Returns:
            バージョン情報（抽出できない場合はNone）
        """
        # "ffmpeg version X.Y.Z" のパターンを探す
        match = re.search(r"ffmpeg version ([^\s]+)", output)
        if match:
            return match.group(1)
        return None
