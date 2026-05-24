"""セットアップシステムサブルーター。

責務：システムソフトウェアのチェック・セットアップ系エンドポイント。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from structlog.stdlib import BoundLogger

from splat_replay.application.services import (
    ErrorHandler,
    SystemCheckService,
    SystemSetupService,
)
from splat_replay.interface.web.schemas import SystemCheckResponse

from .setup_error_handling import handle_endpoint_error


def create_setup_system_router(
    system_check_service: SystemCheckService,
    system_setup_service: SystemSetupService,
    error_handler: ErrorHandler,
    logger: BoundLogger,
) -> APIRouter:
    """セットアップシステムルーターを作成する。"""
    router = APIRouter()

    @router.post("/system/setup/ffmpeg", response_model=SystemCheckResponse)
    async def setup_ffmpeg() -> SystemCheckResponse:
        """FFmpegのセットアップを実行する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to setup FFmpeg"
        ):
            result = system_setup_service.setup_ffmpeg()
            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(result.installation_path)
                if result.installation_path
                else None,
                error_message=result.error_message,
            )

    @router.post("/system/setup/obs", response_model=SystemCheckResponse)
    async def setup_obs() -> SystemCheckResponse:
        """OBS Studioのセットアップを実行する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to setup OBS"
        ):
            result = system_setup_service.setup_obs()
            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(result.installation_path)
                if result.installation_path
                else None,
                error_message=result.error_message,
            )

    @router.post("/system/setup/tesseract", response_model=SystemCheckResponse)
    async def setup_tesseract() -> SystemCheckResponse:
        """Tesseractのセットアップを実行する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to setup Tesseract"
        ):
            result = system_setup_service.setup_tesseract()
            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(result.installation_path)
                if result.installation_path
                else None,
                error_message=result.error_message,
            )

    @router.get("/system/check/{software}", response_model=SystemCheckResponse)
    async def check_system_software(software: str) -> SystemCheckResponse:
        """システムソフトウェアのインストール状態をチェックする。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to check system software"
        ):
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

    return router
