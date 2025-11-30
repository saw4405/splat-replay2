"""インストーラーエラークラス。"""

from __future__ import annotations

from typing import Optional


class InstallerError(Exception):
    """インストーラーエラーの基底クラス。"""

    def __init__(
        self,
        message: str,
        error_code: str,
        recovery_action: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        """エラーを初期化する。

        Args:
            message: エラーメッセージ
            error_code: エラーコード
            recovery_action: 回復アクション（オプション）
            cause: 原因となった例外（オプション）
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.recovery_action = recovery_action
        self.cause = cause


class SystemCheckError(InstallerError):
    """システムチェックエラー。"""

    def __init__(
        self,
        message: str,
        software_name: str,
        recovery_action: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        """エラーを初期化する。

        Args:
            message: エラーメッセージ
            software_name: ソフトウェア名
            recovery_action: 回復アクション（オプション）
            cause: 原因となった例外（オプション）
        """
        super().__init__(
            message=message,
            error_code=f"SYSTEM_CHECK_{software_name.upper()}",
            recovery_action=recovery_action,
            cause=cause,
        )
        self.software_name = software_name


class InstallationStateError(InstallerError):
    """インストール状態エラー。"""

    def __init__(
        self,
        message: str,
        recovery_action: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        """エラーを初期化する。

        Args:
            message: エラーメッセージ
            recovery_action: 回復アクション（オプション）
            cause: 原因となった例外（オプション）
        """
        super().__init__(
            message=message,
            error_code="INSTALLATION_STATE",
            recovery_action=recovery_action,
            cause=cause,
        )


class FileOperationError(InstallerError):
    """ファイル操作エラー。"""

    def __init__(
        self,
        message: str,
        file_path: str,
        recovery_action: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        """エラーを初期化する。

        Args:
            message: エラーメッセージ
            file_path: ファイルパス
            recovery_action: 回復アクション（オプション）
            cause: 原因となった例外（オプション）
        """
        super().__init__(
            message=message,
            error_code="FILE_OPERATION",
            recovery_action=recovery_action,
            cause=cause,
        )
        self.file_path = file_path


class NetworkError(InstallerError):
    """ネットワークエラー。"""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        recovery_action: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        """エラーを初期化する。

        Args:
            message: エラーメッセージ
            url: URL（オプション）
            recovery_action: 回復アクション（オプション）
            cause: 原因となった例外（オプション）
        """
        super().__init__(
            message=message,
            error_code="NETWORK",
            recovery_action=recovery_action,
            cause=cause,
        )
        self.url = url


class UserCancelledError(InstallerError):
    """ユーザーキャンセルエラー。"""

    def __init__(
        self,
        message: str = "ユーザーによってキャンセルされました",
    ) -> None:
        """エラーを初期化する。

        Args:
            message: エラーメッセージ
        """
        super().__init__(
            message=message,
            error_code="USER_CANCELLED",
            recovery_action="インストーラーを再起動してください",
        )
