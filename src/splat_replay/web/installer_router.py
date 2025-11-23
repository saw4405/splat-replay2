"""インストーラーAPIルーター。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from structlog.stdlib import BoundLogger

from splat_replay.application.services import (
    ErrorHandler,
    InstallerService,
    SystemCheckService,
    SystemSetupService,
)
from splat_replay.domain.models import InstallationStep


class InstallationStatusResponse(BaseModel):
    """インストール状態レスポンス。"""

    is_completed: bool
    current_step: str
    completed_steps: list[str]
    skipped_steps: list[str]
    progress_percentage: float
    remaining_steps: list[str]
    step_details: dict[str, dict[str, bool]]


class StepInfoResponse(BaseModel):
    """ステップ情報レスポンス。"""

    step: str
    display_name: str
    is_completed: bool
    is_skipped: bool


class SystemCheckResponse(BaseModel):
    """システムチェックレスポンス。"""

    is_installed: bool
    version: str | None = None
    installation_path: str | None = None
    error_message: str | None = None


class ErrorResponse(BaseModel):
    """エラーレスポンス。"""

    error_code: str
    message: str
    user_message: str
    recovery_actions: list[str]
    is_recoverable: bool


def create_installer_router(
    installer_service: InstallerService,
    system_check_service: SystemCheckService,
    system_setup_service: SystemSetupService,
    error_handler: ErrorHandler,
    logger: BoundLogger,
) -> APIRouter:
    """インストーラーAPIルーターを作成する。

    Args:
        installer_service: インストーラーサービス
        system_check_service: システムチェックサービス
        system_setup_service: システムセットアップサービス
        error_handler: エラーハンドラー
        logger: ロガー

    Returns:
        APIRouter
    """
    router = APIRouter(prefix="/installer", tags=["installer"])

    @router.get("/status", response_model=InstallationStatusResponse)
    async def get_installation_status() -> InstallationStatusResponse:
        """インストール状態を取得する。"""
        try:
            state = installer_service.check_installation_status()

            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()],
                step_details=state.step_details,
            )
        except Exception as e:
            logger.error("Failed to get installation status", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/start", response_model=InstallationStatusResponse)
    async def start_installation() -> InstallationStatusResponse:
        """インストーラーを開始する。"""
        try:
            state = installer_service.start_installation()

            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()],
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
        """インストールを完了する。"""
        try:
            state = installer_service.complete_installation()

            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[step.value for step in state.completed_steps],
                skipped_steps=[step.value for step in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[
                    step.value for step in state.get_remaining_steps()],
                step_details=state.step_details,
            )
        except Exception as e:
            logger.error("Failed to complete installation", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.get("/steps", response_model=list[StepInfoResponse])
    async def get_steps() -> list[StepInfoResponse]:
        """全ステップ情報を取得する。"""
        try:
            state = installer_service.check_installation_status()

            steps_info = []
            for step in InstallationStep.get_all_steps():
                steps_info.append(
                    StepInfoResponse(
                        step=step.value,
                        display_name=step.get_display_name(),
                        is_completed=state.is_step_completed(step),
                        is_skipped=state.is_step_skipped(step),
                    )
                )

            return steps_info
        except Exception as e:
            logger.error("Failed to get steps", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/steps/{step}/complete", response_model=InstallationStatusResponse)
    async def mark_step_completed(step: str) -> InstallationStatusResponse:
        """ステップを完了済みとしてマークする。"""
        try:
            step_enum = InstallationStep(step)
            state = installer_service.mark_step_completed(step_enum)

            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[s.value for s in state.completed_steps],
                skipped_steps=[s.value for s in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[s.value for s in state.get_remaining_steps()],
                step_details=state.step_details,
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid step: {step}",
            )
        except Exception as e:
            logger.error("Failed to mark step completed",
                         step=step, error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/steps/{step}/substeps/{substep_id}", response_model=InstallationStatusResponse)
    async def mark_substep_completed(
        step: str, substep_id: str, completed: bool = True
    ) -> InstallationStatusResponse:
        """サブステップを完了済みとしてマークする。"""
        try:
            step_enum = InstallationStep(step)
            state = installer_service.mark_substep_completed(
                step_enum, substep_id, completed
            )

            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[s.value for s in state.completed_steps],
                skipped_steps=[s.value for s in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[s.value for s in state.get_remaining_steps()],
                step_details=state.step_details,
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid step: {step}",
            )
        except Exception as e:
            logger.error(
                "Failed to mark substep completed",
                step=step,
                substep_id=substep_id,
                error=str(e),
            )
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/steps/{step}/skip", response_model=InstallationStatusResponse)
    async def skip_step(step: str) -> InstallationStatusResponse:
        """ステップをスキップする。"""
        try:
            # 現在のステップを確認
            current_step = installer_service.get_current_step()
            if current_step.value != step:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot skip step {step}. Current step is {current_step.value}",
                )

            state = installer_service.skip_current_step()

            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[s.value for s in state.completed_steps],
                skipped_steps=[s.value for s in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[s.value for s in state.get_remaining_steps()],
                step_details=state.step_details,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to skip step", step=step, error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/navigation/next", response_model=InstallationStatusResponse)
    async def proceed_to_next_step() -> InstallationStatusResponse:
        """次のステップに進む。"""
        try:
            state = installer_service.proceed_to_next_step()

            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[s.value for s in state.completed_steps],
                skipped_steps=[s.value for s in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[s.value for s in state.get_remaining_steps()],
                step_details=state.step_details,
            )
        except ValueError as e:
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

    @router.post("/navigation/previous", response_model=InstallationStatusResponse)
    async def go_back_to_previous_step() -> InstallationStatusResponse:
        """前のステップに戻る。"""
        try:
            state = installer_service.go_back_to_previous_step()

            return InstallationStatusResponse(
                is_completed=state.is_completed,
                current_step=state.current_step.value,
                completed_steps=[s.value for s in state.completed_steps],
                skipped_steps=[s.value for s in state.skipped_steps],
                progress_percentage=state.get_progress_percentage(),
                remaining_steps=[s.value for s in state.get_remaining_steps()],
                step_details=state.step_details,
            )
        except ValueError as e:
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

    @router.get("/system/check/obs", response_model=SystemCheckResponse)
    async def check_obs() -> SystemCheckResponse:
        """OBSのインストール状態を確認する。"""
        try:
            result = system_check_service.check_obs_installation()

            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(
                    result.installation_path) if result.installation_path else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to check OBS", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.get("/system/check/ffmpeg", response_model=SystemCheckResponse)
    async def check_ffmpeg() -> SystemCheckResponse:
        """FFMPEGのインストール状態を確認する。"""
        try:
            result = system_check_service.check_ffmpeg_installation()

            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(
                    result.installation_path) if result.installation_path else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to check FFMPEG", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.get("/system/check/ndi", response_model=SystemCheckResponse)
    async def check_ndi() -> SystemCheckResponse:
        """NDI Runtimeのインストール状態を確認する。"""
        try:
            result = system_check_service.check_ndi_runtime_installation()

            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(
                    result.installation_path) if result.installation_path else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to check NDI Runtime", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.get("/system/check/tesseract", response_model=SystemCheckResponse)
    async def check_tesseract() -> SystemCheckResponse:
        """Tesseractのインストール状態を確認する。"""
        try:
            result = system_check_service.check_tesseract_installation()

            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(
                    result.installation_path) if result.installation_path else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to check Tesseract", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.get("/system/check/font", response_model=SystemCheckResponse)
    async def check_font() -> SystemCheckResponse:
        """フォントのインストール状態を確認する。"""
        try:
            result = system_check_service.check_font_installation()

            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(
                    result.installation_path) if result.installation_path else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to check font", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.get("/system/check/youtube", response_model=SystemCheckResponse)
    async def check_youtube() -> SystemCheckResponse:
        """YouTube API 認証情報の存在を確認する。"""
        try:
            result = system_check_service.check_youtube_credentials()

            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(
                    result.installation_path) if result.installation_path else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to check YouTube credentials", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/system/setup/ffmpeg", response_model=SystemCheckResponse)
    async def setup_ffmpeg() -> SystemCheckResponse:
        """FFMPEGのセットアップ（PATH追加など）を行う。"""
        try:
            result = system_setup_service.setup_ffmpeg()

            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(
                    result.installation_path) if result.installation_path else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to setup FFMPEG", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    @router.post("/system/setup/tesseract", response_model=SystemCheckResponse)
    async def setup_tesseract() -> SystemCheckResponse:
        """Tesseractのセットアップ（PATH追加など）を行う。"""
        try:
            result = system_setup_service.setup_tesseract()

            return SystemCheckResponse(
                is_installed=result.is_installed,
                version=result.version,
                installation_path=str(
                    result.installation_path) if result.installation_path else None,
                error_message=result.error_message,
            )
        except Exception as e:
            logger.error("Failed to setup Tesseract", error=str(e))
            error_response = error_handler.handle_error(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response.user_message,
            )

    return router

