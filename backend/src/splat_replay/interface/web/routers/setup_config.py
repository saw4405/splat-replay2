"""セットアップ設定サブルーター。

責務：OBS設定・デバイス設定・YouTube設定系エンドポイント。
"""

from __future__ import annotations

from fastapi import APIRouter
from structlog.stdlib import BoundLogger

from splat_replay.application.services import (
    AutoUploader,
    DeviceChecker,
    ErrorHandler,
    RecordingPreparationService,
)
from splat_replay.interface.web.schemas import (
    CaptureDeviceRequest,
    CaptureDeviceSaveResponse,
    MessageResponse,
    MicrophoneDeviceListResponse,
    OBSConfigResponse,
    OBSWebSocketPasswordRequest,
    VideoDeviceListResponse,
    YouTubePrivacyStatusRequest,
)

from .setup_error_handling import handle_endpoint_error


def create_setup_config_router(
    recording_preparation_service: RecordingPreparationService,
    device_checker: DeviceChecker,
    auto_uploader: AutoUploader,
    error_handler: ErrorHandler,
    logger: BoundLogger,
) -> APIRouter:
    """セットアップ設定ルーターを作成する。"""
    router = APIRouter()

    @router.get("/config/obs", response_model=OBSConfigResponse)
    async def get_obs_config() -> OBSConfigResponse:
        """OBS設定を取得する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to get OBS config"
        ):
            config = recording_preparation_service.get_obs_config()
            return OBSConfigResponse(**config)

    @router.post(
        "/config/obs/websocket-password", response_model=MessageResponse
    )
    async def save_obs_websocket_password(
        request: OBSWebSocketPasswordRequest,
    ) -> MessageResponse:
        """OBS WebSocketパスワードを保存する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to save OBS WebSocket password"
        ):
            recording_preparation_service.save_obs_websocket_password(
                request.password
            )
            return MessageResponse(
                message="OBS WebSocket password saved successfully"
            )

    @router.get("/devices/video", response_model=VideoDeviceListResponse)
    async def list_video_devices() -> VideoDeviceListResponse:
        """ビデオキャプチャデバイス一覧を取得する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to list video devices"
        ):
            devices = device_checker.list_video_capture_devices()
            return VideoDeviceListResponse(devices=devices)

    @router.get("/devices/audio", response_model=MicrophoneDeviceListResponse)
    async def list_microphone_devices() -> MicrophoneDeviceListResponse:
        """マイクデバイス一覧を取得する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to list microphone devices"
        ):
            devices = device_checker.list_microphone_devices()
            return MicrophoneDeviceListResponse(devices=devices)

    @router.post(
        "/config/capture-device", response_model=CaptureDeviceSaveResponse
    )
    async def save_capture_device(
        request: CaptureDeviceRequest,
    ) -> CaptureDeviceSaveResponse:
        """キャプチャデバイス名を保存する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to save capture device"
        ):
            recording_preparation_service.save_capture_device(
                request.device_name
            )
            device_checker.update_settings(
                recording_preparation_service.get_capture_device_settings()
            )
            return CaptureDeviceSaveResponse(
                message="Capture device saved successfully",
            )

    @router.post(
        "/config/youtube/privacy-status", response_model=MessageResponse
    )
    async def save_youtube_privacy_status(
        request: YouTubePrivacyStatusRequest,
    ) -> MessageResponse:
        """YouTube公開設定を保存する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to save YouTube privacy status"
        ):
            auto_uploader.set_privacy_status(request.privacy_status)
            return MessageResponse(
                message="YouTube privacy status saved successfully"
            )

    return router
