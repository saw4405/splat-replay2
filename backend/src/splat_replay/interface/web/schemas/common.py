"""Common schemas for Web API.

機能横断的に使用される共通スキーマを定義する。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

__all__ = [
    "EditUploadState",
    "EditUploadStatus",
    "EditUploadTriggerResponse",
]

EditUploadState = Literal["idle", "running", "succeeded", "failed"]


class EditUploadStatus(BaseModel):
    """編集アップロード状態"""

    state: EditUploadState
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


class EditUploadTriggerResponse(BaseModel):
    """編集アップロード開始レスポンス"""

    accepted: bool
    status: EditUploadStatus
    message: Optional[str] = None
