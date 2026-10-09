"""FLAC コマンドのインストール状態チェッカー。"""

from __future__ import annotations

from splat_replay.application.interfaces import (
    CommandExecutionError,
    LoggerPort,
    SystemCommandPort,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)


class FLACChecker:
    """PATH から FLAC を実行できるか確認する。"""

    def __init__(
        self, command_port: SystemCommandPort, logger: LoggerPort
    ) -> None:
        self._command_port = command_port
        self._logger = logger

    def check(self) -> SoftwareCheckResult:
        """flac --version が成功したときだけ導入済みとする。"""
        if not self._command_port.check_command_exists("flac"):
            return SoftwareCheckResult(
                is_installed=False,
                error_message="FLAC コマンドが PATH に見つかりませんでした",
            )

        try:
            result = self._command_port.execute_command(
                ["flac", "--version"], timeout=5.0
            )
        except CommandExecutionError as exc:
            self._logger.warning("FLAC version check failed", error=str(exc))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"FLAC の確認中にエラーが発生しました: {exc}",
            )

        if not result.success:
            return SoftwareCheckResult(
                is_installed=False,
                error_message="FLAC の実行確認に失敗しました",
            )

        version = result.stdout.strip().splitlines()
        return SoftwareCheckResult(
            is_installed=True,
            version=version[0] if version else None,
        )
