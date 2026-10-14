"""Setup-related schemas for Web API."""

from __future__ import annotations

import platform
from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "CaptureDeviceRequest",
    "CaptureDeviceSaveResponse",
    "ErrorResponse",
    "InstallationStatusResponse",
    "MessageResponse",
    "MicrophoneDeviceListResponse",
    "OBSConfigResponse",
    "OBSWebSocketPasswordRequest",
    "RequiredSetupIssueResponse",
    "StepInfoResponse",
    "SystemCheckResponse",
    "VideoDeviceListResponse",
    "YouTubePrivacyStatusRequest",
]


def _get_server_platform() -> Literal["windows", "macos", "unknown"]:
    system_name = platform.system()
    if system_name == "Windows":
        return "windows"
    if system_name == "Darwin":
        return "macos"
    return "unknown"


class RequiredSetupIssueResponse(BaseModel):
    code: str
    step: str
    substep_id: str
    message: str


class InstallationStatusResponse(BaseModel):
    is_completed: bool
    current_step: str
    completed_steps: list[str]
    skipped_steps: list[str]
    progress_percentage: float
    remaining_steps: list[str]
    step_details: dict[str, dict[str, bool]]
    required_setup_issues: list[RequiredSetupIssueResponse] = Field(
        default_factory=list
    )
    server_platform: Literal["windows", "macos", "unknown"] = Field(
        default_factory=_get_server_platform
    )


class StepInfoResponse(BaseModel):
    step: str
    display_name: str
    is_completed: bool
    is_skipped: bool


class SystemCheckResponse(BaseModel):
    is_installed: bool
    version: str | None = None
    installation_path: str | None = None
    error_message: str | None = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    user_message: str
    recovery_actions: list[str]
    is_recoverable: bool


class MessageResponse(BaseModel):
    message: str


class OBSConfigResponse(BaseModel):
    websocket_password: str
    capture_device_name: str


class OBSWebSocketPasswordRequest(BaseModel):
    password: str


class VideoDeviceListResponse(BaseModel):
    devices: list[str]


class MicrophoneDeviceListResponse(BaseModel):
    devices: list[str]


class CaptureDeviceRequest(BaseModel):
    device_name: str


class CaptureDeviceSaveResponse(MessageResponse):
    pass


YouTubePrivacyStatus = Literal["private", "unlisted", "public"]


class YouTubePrivacyStatusRequest(BaseModel):
    privacy_status: YouTubePrivacyStatus
