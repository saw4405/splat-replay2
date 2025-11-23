"""エラーハンドラーサービス。"""

from __future__ import annotations

from typing import Optional

from structlog.stdlib import BoundLogger

from splat_replay.application.services.installer_errors import (
    FileOperationError,
    InstallerError,
    InstallationStateError,
    NetworkError,
    SystemCheckError,
    UserCancelledError,
)


class ErrorResponse:
    """エラーレスポンス。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        user_message: str,
        recovery_actions: list[str],
        is_recoverable: bool,
    ) -> None:
        """エラーレスポンスを初期化する。

        Args:
            error_code: エラーコード
            message: 技術的なエラーメッセージ
            user_message: ユーザー向けメッセージ
            recovery_actions: 回復アクションのリスト
            is_recoverable: 回復可能かどうか
        """
        self.error_code = error_code
        self.message = message
        self.user_message = user_message
        self.recovery_actions = recovery_actions
        self.is_recoverable = is_recoverable


class ErrorHandler:
    """エラー処理の統一化を行うサービス。"""

    def __init__(self, logger: BoundLogger) -> None:
        """エラーハンドラーを初期化する。

        Args:
            logger: ロガー
        """
        self._logger = logger

    def handle_error(
        self,
        error: Exception,
        context: Optional[dict[str, str]] = None,
    ) -> ErrorResponse:
        """エラーを処理してエラーレスポンスを生成する。

        Args:
            error: 発生したエラー
            context: エラーコンテキスト（オプション）

        Returns:
            エラーレスポンス
        """
        # エラーをログに記録
        self.log_error(error, context or {})

        # エラーの種類に応じて処理
        if isinstance(error, InstallerError):
            return self._handle_installer_error(error)
        else:
            return self._handle_generic_error(error)

    def suggest_recovery_action(self, error: InstallerError) -> list[str]:
        """エラーに対する回復アクションを提案する。

        Args:
            error: インストーラーエラー

        Returns:
            回復アクションのリスト
        """
        actions: list[str] = []

        # エラー固有の回復アクション
        if error.recovery_action:
            actions.append(error.recovery_action)

        # エラータイプ別の推奨アクション
        if isinstance(error, SystemCheckError):
            actions.extend(self._get_system_check_recovery_actions(error))
        elif isinstance(error, FileOperationError):
            actions.extend(self._get_file_operation_recovery_actions(error))
        elif isinstance(error, NetworkError):
            actions.extend(self._get_network_recovery_actions(error))
        elif isinstance(error, InstallationStateError):
            actions.extend(
                self._get_installation_state_recovery_actions(error))
        elif isinstance(error, UserCancelledError):
            actions.extend(["インストーラーを再起動してください"])

        # 共通の回復アクション
        if not actions:
            actions.append("問題が解決しない場合は、サポートにお問い合わせください")

        return actions

    def log_error(
        self,
        error: Exception,
        context: dict[str, str],
    ) -> None:
        """エラーをログに記録する。

        Args:
            error: 発生したエラー
            context: エラーコンテキスト
        """
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            **context,
        }

        if isinstance(error, InstallerError):
            error_info["error_code"] = error.error_code
            if error.cause:
                error_info["cause"] = str(error.cause)

        self._logger.error(
            "Installer error occurred",
            **error_info,
            exc_info=True,
        )

    def _handle_installer_error(self, error: InstallerError) -> ErrorResponse:
        """インストーラーエラーを処理する。

        Args:
            error: インストーラーエラー

        Returns:
            エラーレスポンス
        """
        recovery_actions = self.suggest_recovery_action(error)
        user_message = self._get_user_friendly_message(error)

        return ErrorResponse(
            error_code=error.error_code,
            message=error.message,
            user_message=user_message,
            recovery_actions=recovery_actions,
            is_recoverable=not isinstance(error, UserCancelledError),
        )

    def _handle_generic_error(self, error: Exception) -> ErrorResponse:
        """一般的なエラーを処理する。

        Args:
            error: エラー

        Returns:
            エラーレスポンス
        """
        return ErrorResponse(
            error_code="UNKNOWN",
            message=str(error),
            user_message="予期しないエラーが発生しました",
            recovery_actions=[
                "アプリケーションを再起動してください",
                "問題が解決しない場合は、サポートにお問い合わせください",
            ],
            is_recoverable=True,
        )

    def _get_user_friendly_message(self, error: InstallerError) -> str:
        """ユーザーフレンドリーなエラーメッセージを取得する。

        Args:
            error: インストーラーエラー

        Returns:
            ユーザー向けメッセージ
        """
        if isinstance(error, SystemCheckError):
            return f"{error.software_name} の確認中にエラーが発生しました"
        elif isinstance(error, FileOperationError):
            return "ファイル操作中にエラーが発生しました"
        elif isinstance(error, NetworkError):
            return "ネットワーク接続中にエラーが発生しました"
        elif isinstance(error, InstallationStateError):
            return "インストール状態の管理中にエラーが発生しました"
        elif isinstance(error, UserCancelledError):
            return error.message
        else:
            return error.message

    def _get_system_check_recovery_actions(
        self,
        error: SystemCheckError,
    ) -> list[str]:
        """システムチェックエラーの回復アクションを取得する。

        Args:
            error: システムチェックエラー

        Returns:
            回復アクションのリスト
        """
        return [
            f"{error.software_name} がインストールされているか確認してください",
            "環境変数PATHが正しく設定されているか確認してください",
            "アプリケーションを管理者権限で実行してみてください",
        ]

    def _get_file_operation_recovery_actions(
        self,
        error: FileOperationError,
    ) -> list[str]:
        """ファイル操作エラーの回復アクションを取得する。

        Args:
            error: ファイル操作エラー

        Returns:
            回復アクションのリスト
        """
        return [
            f"ファイル '{error.file_path}' へのアクセス権限を確認してください",
            "ディスクの空き容量を確認してください",
            "ファイルが他のプログラムで使用されていないか確認してください",
        ]

    def _get_network_recovery_actions(
        self,
        error: NetworkError,
    ) -> list[str]:
        """ネットワークエラーの回復アクションを取得する。

        Args:
            error: ネットワークエラー

        Returns:
            回復アクションのリスト
        """
        actions = [
            "インターネット接続を確認してください",
            "ファイアウォール設定を確認してください",
        ]

        if error.url:
            actions.append(f"URL '{error.url}' にアクセスできるか確認してください")

        return actions

    def _get_installation_state_recovery_actions(
        self,
        error: InstallationStateError,
    ) -> list[str]:
        """インストール状態エラーの回復アクションを取得する。

        Args:
            error: インストール状態エラー

        Returns:
            回復アクションのリスト
        """
        return [
            "インストーラーを再起動してください",
            "設定ファイルが破損している可能性があります",
            "必要に応じてインストール状態をリセットしてください",
        ]
