"""エラーロギングサービス。"""

from __future__ import annotations

from splat_replay.application.interfaces import LoggerPort
from splat_replay.application.services.setup.setup_errors import SetupError


class ErrorLogger:
    """エラーをログに記録するサービス。

    責務:
    - 構造化ログの記録
    - エラーコンテキスト情報の整形
    - SetupError固有の情報抽出
    """

    def __init__(self, logger: LoggerPort) -> None:
        """エラーロガーを初期化する。

        Args:
            logger: ロガーポート
        """
        self._logger = logger

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

        if isinstance(error, SetupError):
            error_info["error_code"] = error.error_code
            if error.cause:
                error_info["cause"] = str(error.cause)

        self._logger.error(
            "Setup error occurred",
            **error_info,
            exc_info=True,
        )
