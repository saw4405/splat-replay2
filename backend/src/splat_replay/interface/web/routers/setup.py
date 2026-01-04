"""セットアップAPIルーター。

責務：
- セットアップ状態の管理
- システムチェック・セットアップの実行
- OBS / YouTube 設定
- デバイス選択
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from structlog.stdlib import BoundLogger

from splat_replay.application.services import (
    AutoUploader,
    DeviceChecker,
    ErrorHandler,
    RecordingPreparationService,
    SetupService,
    SystemCheckService,
    SystemSetupService,
)
from splat_replay.domain.models import SetupStep
from splat_replay.interface.web.schemas import (
    CaptureDeviceRequest,
    InstallationStatusResponse,
    MessageResponse,
    OBSConfigResponse,
    OBSWebSocketPasswordRequest,
    SystemCheckResponse,
    VideoDeviceListResponse,
    YouTubePrivacyStatusRequest,
)

__all__ = ["create_setup_router"]


class SubstepCompletionRequest(BaseModel):
    """サブステップ完了リクエスト。"""

    completed: bool = True


def create_setup_router(
    setup_service: SetupService,
    system_check_service: SystemCheckService,
    system_setup_service: SystemSetupService,
    error_handler: ErrorHandler,
    logger: BoundLogger,
    device_checker: DeviceChecker,
    recording_preparation_service: RecordingPreparationService,
    auto_uploader: AutoUploader,
) -> APIRouter:
    """セットアップAPIルーターを作成する。

    Args:
        setup_service: セットアップサービス
        system_check_service: システムチェックサービス
        system_setup_service: システムセットアップサービス
        error_handler: エラーハンドラー
        logger: ロガー
        device_checker: デバイスチェッカー
        recording_preparation_service: 録画準備サービス
        auto_uploader: 自動アップローダー

    Returns:
        APIRouter
    """
    router = APIRouter(prefix="/setup", tags=["setup"])

    @router.get("/status", response_model=InstallationStatusResponse)
    async def get_installation_status() -> InstallationStatusResponse:
        """現在のセットアップ状態を取得する。"""
        try:
            state = setup_service.check_installation_status()
            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()
                ],
                step_details=state.step_details,
            )
        except Exception as e:
            logger.error("Failed to get installation status", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/navigation/next", response_model=InstallationStatusResponse)
    async def navigate_next() -> InstallationStatusResponse:
        """次のステップに進む。"""
        try:
            state = setup_service.proceed_to_next_step()
            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value
                if not state.is_completed
                else "completed",
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()
                ],
                step_details=state.step_details,
            )
        except ValueError as e:
            logger.error("Failed to proceed to next step", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            logger.error("Failed to proceed to next step", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post(
        "/navigation/previous", response_model=InstallationStatusResponse
    )
    async def navigate_back() -> InstallationStatusResponse:
        """前のステップに戻る。"""
        try:
            state = setup_service.go_back_to_previous_step()
            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()
                ],
                step_details=state.step_details,
            )
        except ValueError as e:
            logger.error("Failed to go back to previous step", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            logger.error("Failed to go back to previous step", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/start", response_model=InstallationStatusResponse)
    async def start_installation() -> InstallationStatusResponse:
        """セットアップを開始する。"""
        try:
            state = setup_service.start_installation()
            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()
                ],
                step_details=state.step_details,
            )
        except Exception as e:
            logger.error("Failed to start installation", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/complete", response_model=InstallationStatusResponse)
    async def complete_installation() -> InstallationStatusResponse:
        """セットアップを完了する。"""
        try:
            state = setup_service.complete_installation()
            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value
                if not state.is_completed
                else "completed",
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()
                ],
                step_details=state.step_details,
            )
        except Exception as e:
            logger.error("Failed to complete installation", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post(
        "/steps/{step_name}/complete",
        response_model=InstallationStatusResponse,
    )
    async def complete_step(step_name: str) -> InstallationStatusResponse:
        """指定されたステップを完了済みとしてマークする。"""
        try:
            # ステップ名をSetupStepに変換
            try:
                step = SetupStep(step_name)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid step name: {step_name}",
                )

            state = setup_service.mark_step_completed(step)
            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()
                ],
                step_details=state.step_details,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Failed to complete step", step=step_name, error=str(e)
            )
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post(
        "/steps/{step_name}/skip", response_model=InstallationStatusResponse
    )
    async def skip_step(step_name: str) -> InstallationStatusResponse:
        """指定されたステップをスキップする。"""
        try:
            state = setup_service.skip_current_step()
            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()
                ],
                step_details=state.step_details,
            )
        except Exception as e:
            logger.error("Failed to skip step", step=step_name, error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post(
        "/steps/{step_name}/substeps/{substep_id}",
        response_model=InstallationStatusResponse,
    )
    async def update_substep_completion(
        step_name: str, substep_id: str, completed: bool = True
    ) -> InstallationStatusResponse:
        """サブステップの完了状態を更新する。"""
        try:
            # ステップ名をSetupStepに変換
            try:
                step = SetupStep(step_name)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid step name: {step_name}",
                )

            state = setup_service.mark_substep_completed(
                step, substep_id, completed
            )
            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()
                ],
                step_details=state.step_details,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Failed to update substep completion",
                step=step_name,
                substep=substep_id,
                error=str(e),
            )
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/system/setup/ffmpeg", response_model=SystemCheckResponse)
    async def setup_ffmpeg() -> SystemCheckResponse:
        """FFmpegのセットアップを実行する。"""
        try:
            result = system_setup_service.setup_ffmpeg()
            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(result.installation_path)
                if result.installation_path
                else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to setup FFmpeg", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/system/setup/obs", response_model=SystemCheckResponse)
    async def setup_obs() -> SystemCheckResponse:
        """OBS Studioのセットアップを実行する。"""
        try:
            result = system_setup_service.setup_obs()
            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(result.installation_path)
                if result.installation_path
                else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to setup OBS", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/system/setup/tesseract", response_model=SystemCheckResponse)
    async def setup_tesseract() -> SystemCheckResponse:
        """Tesseractのセットアップを実行する。"""
        try:
            result = system_setup_service.setup_tesseract()
            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(result.installation_path)
                if result.installation_path
                else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to setup Tesseract", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.get("/system/check/{software}", response_model=SystemCheckResponse)
    async def check_system_software(software: str) -> SystemCheckResponse:
        """システムソフトウェアのインストール状態をチェックする。"""
        try:
            if software == "obs":
                result = system_check_service.check_obs_installation()
            elif software == "ffmpeg":
                result = system_check_service.check_ffmpeg_installation()
            elif software == "tesseract":
                result = system_check_service.check_tesseract_installation()
            elif software == "ndi":
                result = system_check_service.check_ndi_runtime_installation()
            elif software == "font":
                result = system_check_service.check_font_installation()
            elif software == "youtube":
                result = system_check_service.check_youtube_credentials()
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown software: {software}",
                )

            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(result.installation_path)
                if result.installation_path
                else None,
                error_message=result.error_message,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Failed to check system software",
                software=software,
                error=str(e),
            )
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.get("/config/obs", response_model=OBSConfigResponse)
    async def get_obs_config() -> OBSConfigResponse:
        """OBS設定を取得する。"""
        try:
            config = recording_preparation_service.get_obs_config()
            return OBSConfigResponse(**config)
        except Exception as e:
            logger.error("Failed to get OBS config", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post(
        "/config/obs/websocket-password", response_model=MessageResponse
    )
    async def save_obs_websocket_password(
        request: OBSWebSocketPasswordRequest,
    ) -> MessageResponse:
        """OBS WebSocketパスワードを保存する。"""
        try:
            recording_preparation_service.save_obs_websocket_password(
                request.password
            )
            return MessageResponse(
                message="OBS WebSocket password saved successfully"
            )
        except Exception as e:
            logger.error("Failed to save OBS WebSocket password", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.get("/devices/video", response_model=VideoDeviceListResponse)
    async def list_video_devices() -> VideoDeviceListResponse:
        """ビデオキャプチャデバイス一覧を取得する。"""
        try:
            devices = device_checker.list_video_capture_devices()
            return VideoDeviceListResponse(devices=devices)
        except Exception as e:
            logger.error("Failed to list video devices", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/config/capture-device", response_model=MessageResponse)
    async def save_capture_device(
        request: CaptureDeviceRequest,
    ) -> MessageResponse:
        """キャプチャデバイス名を保存する。"""
        try:
            recording_preparation_service.save_capture_device(
                request.device_name
            )
            device_checker.update_settings(
                recording_preparation_service.get_capture_device_settings()
            )
            return MessageResponse(message="Capture device saved successfully")
        except Exception as e:
            logger.error("Failed to save capture device", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post(
        "/config/youtube/privacy-status", response_model=MessageResponse
    )
    async def save_youtube_privacy_status(
        request: YouTubePrivacyStatusRequest,
    ) -> MessageResponse:
        """YouTube公開設定を保存する。"""
        try:
            auto_uploader.set_privacy_status(request.privacy_status)
            return MessageResponse(
                message="YouTube privacy status saved successfully"
            )
        except Exception as e:
            logger.error("Failed to save YouTube privacy status", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    return router
