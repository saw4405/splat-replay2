"""System control ports (power, commands, installation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class CommandResult:
    """コマンド実行結果。"""

    return_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """コマンドが成功したかどうか。"""
        return self.return_code == 0


class CommandExecutionError(Exception):
    """コマンド実行エラー。"""

    def __init__(
        self,
        message: str,
        command: list[str],
        cause: Optional[Exception] = None,
    ) -> None:
        """エラーを初期化する。

        Args:
            message: エラーメッセージ
            command: 実行しようとしたコマンド
            cause: 原因となった例外（オプション）
        """
        super().__init__(message)
        self.command = command
        self.cause = cause


class SystemCommandPort(Protocol):
    """システムコマンド実行のポートインターフェース。"""

    def execute_command(
        self,
        command: list[str],
        timeout: Optional[float] = None,
    ) -> CommandResult:
        """Execute system command."""
        ...

    def check_command_exists(self, command: str) -> bool:
        """Check if command exists in system."""
        ...


class EnvironmentPort(Protocol):
    """環境変数操作のポート。"""

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """環境変数を取得する。"""
        ...

    def set(self, name: str, value: str) -> None:
        """環境変数を設定する。"""
        ...


class PowerPort(Protocol):
    """電源制御を行うポート。"""

    async def sleep(self) -> None:
        """Put system to sleep."""
        ...


class InstallationStatePort(Protocol):
    """インストール状態管理ポート。"""

    # Add methods as needed
    pass
