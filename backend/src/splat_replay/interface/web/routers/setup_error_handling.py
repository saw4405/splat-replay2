"""セットアップルーター共通エラーハンドリング。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import HTTPException, status
from structlog.stdlib import BoundLogger

from splat_replay.application.services import ErrorHandler


@asynccontextmanager
async def handle_endpoint_error(
    logger: BoundLogger, error_handler: ErrorHandler, operation: str
) -> AsyncIterator[None]:
    """エンドポイント共通のエラーハンドリング。

    ValueError → 400, HTTPException → 再送出, その他 → 500
    """
    try:
        yield
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(operation, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(operation, error=str(e))
        error_response = error_handler.handle_error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.user_message,
        )
