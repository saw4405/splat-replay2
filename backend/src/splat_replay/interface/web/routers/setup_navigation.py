"""セットアップナビゲーションサブルーター。

責務：セットアップ状態管理・ナビゲーション系エンドポイント。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from structlog.stdlib import BoundLogger

from splat_replay.application.services import ErrorHandler, SetupService
from splat_replay.domain.models import SetupStep
from splat_replay.interface.web.schemas import InstallationStatusResponse

from .setup_error_handling import handle_endpoint_error


def create_setup_navigation_router(
    setup_service: SetupService,
    error_handler: ErrorHandler,
    logger: BoundLogger,
) -> APIRouter:
    """セットアップナビゲーションルーターを作成する。"""
    router = APIRouter()

    @router.get("/status", response_model=InstallationStatusResponse)
    async def get_installation_status() -> InstallationStatusResponse:
        """現在のセットアップ状態を取得する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to get installation status"
        ):
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

    @router.post("/navigation/next", response_model=InstallationStatusResponse)
    async def navigate_next() -> InstallationStatusResponse:
        """次のステップに進む。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to proceed to next step"
        ):
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

    @router.post(
        "/navigation/previous", response_model=InstallationStatusResponse
    )
    async def navigate_back() -> InstallationStatusResponse:
        """前のステップに戻る。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to go back to previous step"
        ):
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

    @router.post("/start", response_model=InstallationStatusResponse)
    async def start_installation() -> InstallationStatusResponse:
        """セットアップを開始する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to start installation"
        ):
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

    @router.post("/complete", response_model=InstallationStatusResponse)
    async def complete_installation() -> InstallationStatusResponse:
        """セットアップを完了する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to complete installation"
        ):
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

    @router.post(
        "/steps/{step_name}/complete",
        response_model=InstallationStatusResponse,
    )
    async def complete_step(step_name: str) -> InstallationStatusResponse:
        """指定されたステップを完了済みとしてマークする。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to complete step"
        ):
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

    @router.post(
        "/steps/{step_name}/skip", response_model=InstallationStatusResponse
    )
    async def skip_step(step_name: str) -> InstallationStatusResponse:
        """指定されたステップをスキップする。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to skip step"
        ):
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

    @router.post(
        "/steps/{step_name}/substeps/{substep_id}",
        response_model=InstallationStatusResponse,
    )
    async def update_substep_completion(
        step_name: str, substep_id: str, completed: bool = True
    ) -> InstallationStatusResponse:
        """サブステップの完了状態を更新する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to update substep completion"
        ):
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

    return router
