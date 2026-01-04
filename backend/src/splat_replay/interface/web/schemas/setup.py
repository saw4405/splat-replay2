"""Setup-related schemas for Web API.

セットアップ機能に関するリクエスト/レスポンス スキーマを定義する。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

__all__ = [
    "InstallationStatusResponse",
    "StepInfoResponse",
    "SystemCheckResponse",
    "ErrorResponse",
    "MessageResponse",
    "OBSConfigResponse",
    "OBSWebSocketPasswordRequest",
    "VideoDeviceListResponse",
    "CaptureDeviceRequest",
    "YouTubePrivacyStatusRequest",
]


class InstallationStatusResponse(BaseModel):
    """セットアップ状態レスポンス"""

    is_completed: bool
    current_step: str
    completed_steps: list[str]
    skipped_steps: list[str]
    progress_percentage: float
    remaining_steps: list[str]
    step_details: dict[str, dict[str, bool]]


class StepInfoResponse(BaseModel):
    """ステップ情報レスポンス"""

    step: str
    display_name: str
    is_completed: bool
    is_skipped: bool


class SystemCheckResponse(BaseModel):
    """システムチェックレスポンス"""

    is_installed: bool
    version: str | None = None
    installation_path: str | None = None
    error_message: str | None = None


class ErrorResponse(BaseModel):
    """エラーレスポンス"""

    error_code: str
    message: str
    user_message: str
    recovery_actions: list[str]
    is_recoverable: bool


class MessageResponse(BaseModel):
    """成功メッセージレスポンス"""

    message: str


class OBSConfigResponse(BaseModel):
    """OBS設定レスポンス"""

    websocket_password: str
    capture_device_name: str


class OBSWebSocketPasswordRequest(BaseModel):
    """OBS WebSocketパスワード設定リクエスト"""

    password: str


class VideoDeviceListResponse(BaseModel):
    """ビデオデバイスリストレスポンス"""

    devices: list[str]


class CaptureDeviceRequest(BaseModel):
    """キャプチャデバイス設定リクエスト"""

    device_name: str


YouTubePrivacyStatus = Literal["private", "unlisted", "public"]


class YouTubePrivacyStatusRequest(BaseModel):
    """YouTube公開設定リクエスト"""

    privacy_status: YouTubePrivacyStatus
