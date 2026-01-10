"""Web API 共通エラーハンドラー。

責務：
- ドメイン例外から HTTP レスポンスへの変換
- 統一されたエラーレスポンス形式の提供
- ログ出力の一元化
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from fastapi import HTTPException, status
from pydantic import BaseModel

from splat_replay.domain.exceptions import (
    AuthenticationError,
    ConfigurationError,
    DeviceError,
    DomainError,
    RecordingError,
    ResourceConflictError,
    ResourceNotFoundError,
    RuleViolationError,
    ValidationError,
)

if TYPE_CHECKING:
    from splat_replay.application.interfaces import LoggerPort


class ErrorResponse(BaseModel):
    """統一エラーレスポンス形式。

    フロントエンドは常にこの形式のエラーを受け取る。
    """

    message: str
    """エラーメッセージ（ユーザー向け）"""

    error_code: str | None = None
    """エラーコード（機械可読）"""

    recovery_action: str | None = None
    """復旧方法の提案"""

    field: str | None = None
    """エラーが発生したフィールド（バリデーションエラー用）"""


class WebErrorHandler:
    """Web API 用のエラーハンドラー。

    ドメイン例外を適切な HTTP ステータスコードと
    統一されたエラーレスポンスに変換する。
    """

    def __init__(self, logger: LoggerPort):
        self._logger = logger

    def handle_error(
        self,
        error: Exception,
        *,
        context: str = "",
        log_level: str = "error",
    ) -> NoReturn:
        """エラーを処理し、適切な HTTPException を発生させる。

        Args:
            error: 発生した例外
            context: エラーのコンテキスト（ログ用）
            log_level: ログレベル（"debug" | "info" | "warning" | "error"）

        Raises:
            HTTPException: 常に発生
        """
        # 既に HTTPException の場合はそのまま再送出
        if isinstance(error, HTTPException):
            raise error

        # ドメイン例外の場合
        if isinstance(error, DomainError):
            self._handle_domain_error(error, context, log_level)

        # 予期しない例外の場合
        self._handle_unexpected_error(error, context)

    def _handle_domain_error(
        self,
        error: DomainError,
        context: str,
        log_level: str,
    ) -> NoReturn:
        """ドメイン例外を処理する。"""
        # ステータスコードを決定
        status_code = self._map_domain_error_to_status(error)

        # エラーレスポンスを構築
        error_response = ErrorResponse(
            message=str(error),
            error_code=error.error_code,
            recovery_action=getattr(error, "recovery_action", None),
        )

        # ログ出力
        log_method = getattr(self._logger, log_level, self._logger.error)
        log_method(
            f"ドメインエラー: {context}" if context else "ドメインエラー",
            error=str(error),
            error_code=error.error_code,
            status_code=status_code,
        )

        # HTTPException を発生
        raise HTTPException(
            status_code=status_code,
            detail=error_response.dict(),
        )

    def _handle_unexpected_error(
        self,
        error: Exception,
        context: str,
    ) -> NoReturn:
        """予期しない例外を処理する。"""
        # エラーレスポンスを構築
        error_response = ErrorResponse(
            message="予期しないエラーが発生しました",
            error_code="INTERNAL_SERVER_ERROR",
            recovery_action="しばらく待ってから再度お試しください。問題が続く場合は管理者にお問い合わせください。",
        )

        # ログ出力（詳細情報を含める）
        self._logger.error(
            f"予期しないエラー: {context}" if context else "予期しないエラー",
            error=str(error),
            error_type=type(error).__name__,
            exc_info=True,  # スタックトレースを含める
        )

        # HTTPException を発生
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.dict(),
        )

    @staticmethod
    def _map_domain_error_to_status(error: DomainError) -> int:
        """ドメイン例外を HTTP ステータスコードにマッピングする。"""
        if isinstance(error, ValidationError):
            return status.HTTP_400_BAD_REQUEST

        if isinstance(error, RuleViolationError):
            return status.HTTP_409_CONFLICT

        if isinstance(error, ResourceNotFoundError):
            return status.HTTP_404_NOT_FOUND

        if isinstance(error, ResourceConflictError):
            return status.HTTP_409_CONFLICT

        if isinstance(error, DeviceError):
            return status.HTTP_503_SERVICE_UNAVAILABLE

        if isinstance(error, AuthenticationError):
            return status.HTTP_401_UNAUTHORIZED

        if isinstance(error, ConfigurationError):
            return status.HTTP_500_INTERNAL_SERVER_ERROR

        if isinstance(error, RecordingError):
            return status.HTTP_409_CONFLICT

        # デフォルト
        return status.HTTP_400_BAD_REQUEST
