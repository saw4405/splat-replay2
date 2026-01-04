"""Error handling utilities for Web API.

FastAPI のエラーハンドリングを統一的に行うユーティリティ。
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse


def create_error_response(
    error_code: str,
    message: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    **extra: Any,
) -> JSONResponse:
    """エラーレスポンスを作成する。

    Args:
        error_code: エラーコード
        message: エラーメッセージ
        status_code: HTTP ステータスコード
        **extra: 追加情報

    Returns:
        JSONResponse
    """
    content: Dict[str, Any] = {
        "error_code": error_code,
        "message": message,
    }
    content.update(extra)

    return JSONResponse(
        status_code=status_code,
        content=content,
    )


def raise_http_exception(
    status_code: int,
    message: str,
    **extra: Any,
) -> None:
    """HTTPException を送出する。

    Args:
        status_code: HTTP ステータスコード
        message: エラーメッセージ
        **extra: 追加情報
    """
    detail: Dict[str, Any] = {"message": message}
    detail.update(extra)

    raise HTTPException(
        status_code=status_code,
        detail=detail,
    )


__all__ = [
    "create_error_response",
    "raise_http_exception",
]
