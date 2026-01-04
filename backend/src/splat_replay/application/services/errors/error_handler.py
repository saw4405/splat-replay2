"""エラーハンドラーサービス。"""

from __future__ import annotations

from typing import Optional

from splat_replay.application.interfaces import LoggerPort
from splat_replay.application.services.errors.error_logger import ErrorLogger
from splat_replay.application.services.errors.error_recovery_advisor import (
    ErrorRecoveryAdvisor,
)
from splat_replay.application.services.setup.setup_errors import (
    SetupError,
    UserCancelledError,
)
from splat_replay.domain.exceptions import DomainError


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
    """エラー処理の統一化を行うサービス。

    責務:
    - エラー処理のエントリーポイント
    - エラータイプ別の振り分け
    - ErrorResponseの生成
    """

    def __init__(
        self,
        logger: LoggerPort,
        error_logger: ErrorLogger | None = None,
        recovery_advisor: ErrorRecoveryAdvisor | None = None,
    ) -> None:
        """エラーハンドラーを初期化する。

        Args:
            logger: ロガー
            error_logger: エラーロガー（指定されない場合は自動生成）
            recovery_advisor: 回復アドバイザー（指定されない場合は自動生成）
        """
        self._error_logger = error_logger or ErrorLogger(logger)
        self._recovery_advisor = recovery_advisor or ErrorRecoveryAdvisor()

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
        self._error_logger.log_error(error, context or {})

        # エラーの種類に応じて処理
        if isinstance(error, DomainError):
            return self._handle_domain_error(error)
        elif isinstance(error, SetupError):
            return self._handle_setup_error(error)
        else:
            return self._handle_generic_error(error)

    def _handle_domain_error(self, error: DomainError) -> ErrorResponse:
        """ドメイン例外を処理する。

        Args:
            error: ドメイン例外

        Returns:
            エラーレスポンス
        """
        recovery_actions = (
            self._recovery_advisor.suggest_domain_error_recovery_action(error)
        )
        user_message = self._recovery_advisor.get_domain_error_user_message(
            error
        )

        return ErrorResponse(
            error_code=error.error_code,
            message=str(error),
            user_message=user_message,
            recovery_actions=recovery_actions,
            is_recoverable=self._recovery_advisor.is_domain_error_recoverable(
                error
            ),
        )

    def _handle_setup_error(self, error: SetupError) -> ErrorResponse:
        """セットアップエラーを処理する。

        Args:
            error: セットアップエラー

        Returns:
            エラーレスポンス
        """
        recovery_actions = self._recovery_advisor.suggest_recovery_action(
            error
        )
        user_message = self._recovery_advisor.get_setup_error_user_message(
            error
        )

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
