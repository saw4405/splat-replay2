"""システムコマンド実行アダプター。"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CommandExecutionError,
    CommandResult,
    SystemCommandPort,
)


class SystemCommandAdapter(SystemCommandPort):
    """システムコマンド実行アダプター。"""

    def __init__(self, logger: BoundLogger) -> None:
        """アダプターを初期化する。

        Args:
            logger: ロガー
        """
        self._logger = logger

    def execute_command(
        self,
        command: list[str],
        timeout: Optional[float] = None,
    ) -> CommandResult:
        """システムコマンドを実行する。

        Args:
            command: 実行するコマンドと引数のリスト
            timeout: タイムアウト秒数（Noneの場合は無制限）

        Returns:
            コマンド実行結果

        Raises:
            CommandExecutionError: コマンド実行に失敗した場合
        """
        if not command:
            raise CommandExecutionError(
                "Command list is empty",
                command=[],
            )

        # コマンドインジェクション対策: リストとして渡す
        # shell=Falseを使用してシェル経由での実行を避ける
        self._logger.debug(
            "Executing command",
            command=command,
            timeout=timeout,
        )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,  # コマンドインジェクション対策
                check=False,  # エラーでも例外を投げない
            )

            self._logger.debug(
                "Command executed",
                command=command,
                return_code=result.returncode,
            )

            return CommandResult(
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout} seconds"
            self._logger.error(
                error_msg,
                command=command,
                timeout=timeout,
            )
            raise CommandExecutionError(
                error_msg,
                command=command,
                cause=e,
            )

        except FileNotFoundError as e:
            error_msg = f"Command not found: {command[0]}"
            self._logger.error(
                error_msg,
                command=command,
            )
            raise CommandExecutionError(
                error_msg,
                command=command,
                cause=e,
            )

        except Exception as e:
            error_msg = f"Command execution failed: {e}"
            self._logger.error(
                error_msg,
                command=command,
                exc_info=True,
            )
            raise CommandExecutionError(
                error_msg,
                command=command,
                cause=e,
            )

    def check_command_exists(self, command: str) -> bool:
        """指定されたコマンドが実行可能かどうかを確認する。

        Args:
            command: 確認するコマンド名

        Returns:
            コマンドが実行可能な場合はTrue、そうでなければFalse
        """
        # shutil.whichを使用してコマンドのパスを検索
        command_path = shutil.which(command)
        exists = command_path is not None

        self._logger.debug(
            "Command existence check",
            command=command,
            exists=exists,
            path=command_path,
        )

        return exists
