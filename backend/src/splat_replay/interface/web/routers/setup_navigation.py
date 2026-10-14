"""セットアップナビゲーションサブルーター。

責務：セットアップ状態管理・ナビゲーション系エンドポイント。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool
from structlog.stdlib import BoundLogger

from splat_replay.application.services import ErrorHandler, SetupService
from splat_replay.application.services.setup.required_setup import (
    RequiredSetupIncompleteError,
    RequiredSetupIssue,
)
from splat_replay.domain.models import SetupState, SetupStep
from splat_replay.interface.web.schemas import (
    InstallationStatusResponse,
    RequiredSetupIssueResponse,
)

from .setup_error_handling import handle_endpoint_error


def create_setup_navigation_router(
    setup_service: SetupService,
    error_handler: ErrorHandler,
    logger: BoundLogger,
) -> APIRouter:
    """セットアップナビゲーションルーターを作成する。"""
    router = APIRouter()

    async def make_status_response(
        state: SetupState, *, force_refresh: bool = False
    ) -> InstallationStatusResponse:
        issues = await run_in_threadpool(
            setup_service.get_required_setup_issues,
            force_refresh=force_refresh,
        )
        return _make_status_response(state, issues)

    @router.get("/status", response_model=InstallationStatusResponse)
    async def get_installation_status(
        refresh: bool = False,
    ) -> InstallationStatusResponse:
        """現在のセットアップ状態と必須設定不足を取得する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to get installation status"
        ):
            issues = await run_in_threadpool(
                setup_service.get_required_setup_issues,
                force_refresh=refresh,
                repair_legacy_state=True,
            )
            state = await run_in_threadpool(
                setup_service.check_installation_status
            )
            return _make_status_response(state, issues)

    @router.post("/repair/{code}", response_model=RequiredSetupIssueResponse)
    async def select_required_setup_issue(
        code: str,
    ) -> RequiredSetupIssueResponse:
        """現在の必須不足一覧から修復先を選び、step情報だけ更新する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to select required setup issue"
        ):
            issue = await run_in_threadpool(
                setup_service.select_required_setup_issue, code
            )
            return _issue_response(issue)

    @router.post("/navigation/next", response_model=InstallationStatusResponse)
    async def navigate_next() -> InstallationStatusResponse:
        """次のステップに進む。最終ステップでは必須条件を再検査する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to proceed to next step"
        ):
            try:
                state = await run_in_threadpool(
                    setup_service.proceed_to_next_step
                )
            except RequiredSetupIncompleteError as exc:
                raise _required_setup_http_error(exc) from exc
            return await make_status_response(state)

    @router.post(
        "/navigation/previous", response_model=InstallationStatusResponse
    )
    async def navigate_back() -> InstallationStatusResponse:
        """前のステップに戻る。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to go back to previous step"
        ):
            state = await run_in_threadpool(
                setup_service.go_back_to_previous_step
            )
            return await make_status_response(state)

    @router.post("/start", response_model=InstallationStatusResponse)
    async def start_installation() -> InstallationStatusResponse:
        """新規セットアップを開始する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to start installation"
        ):
            state = await run_in_threadpool(setup_service.start_installation)
            return await make_status_response(state)

    @router.post("/complete", response_model=InstallationStatusResponse)
    async def complete_installation() -> InstallationStatusResponse:
        """必須設定を再検査してセットアップを完了する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to complete installation"
        ):
            try:
                state = await run_in_threadpool(
                    setup_service.complete_installation
                )
            except RequiredSetupIncompleteError as exc:
                raise _required_setup_http_error(exc) from exc
            return await make_status_response(state)

    @router.post(
        "/steps/{step_name}/complete",
        response_model=InstallationStatusResponse,
    )
    async def complete_step(step_name: str) -> InstallationStatusResponse:
        """指定されたステップを完了済みとしてマークする。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to complete step"
        ):
            step = _parse_step(step_name)
            state = await run_in_threadpool(
                setup_service.mark_step_completed, step
            )
            return await make_status_response(state)

    @router.post(
        "/steps/{step_name}/skip", response_model=InstallationStatusResponse
    )
    async def skip_step(step_name: str) -> InstallationStatusResponse:
        """現在のステップをスキップ済みとしてマークする。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to skip step"
        ):
            # route parameter is retained for API compatibility; current state is authoritative.
            state = await run_in_threadpool(setup_service.skip_current_step)
            return await make_status_response(state)

    @router.post(
        "/steps/{step_name}/substeps/{substep_id}",
        response_model=InstallationStatusResponse,
    )
    async def update_substep_completion(
        step_name: str, substep_id: str, completed: bool = True
    ) -> InstallationStatusResponse:
        """サブステップの履歴状態を更新する。"""
        async with handle_endpoint_error(
            logger, error_handler, "Failed to update substep completion"
        ):
            step = _parse_step(step_name)
            state = await run_in_threadpool(
                setup_service.mark_substep_completed,
                step,
                substep_id,
                completed,
            )
            return await make_status_response(state)

    return router


def _parse_step(step_name: str) -> SetupStep:
    try:
        return SetupStep(step_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid step name: {step_name}",
        ) from exc


def _issue_response(issue: RequiredSetupIssue) -> RequiredSetupIssueResponse:
    return RequiredSetupIssueResponse(
        code=issue.code,
        step=issue.step,
        substep_id=issue.substep_id,
        message=issue.message,
    )


def _make_status_response(
    state: SetupState, issues: list[RequiredSetupIssue]
) -> InstallationStatusResponse:
    return InstallationStatusResponse(
        is_completed=state.is_completed,
        current_step=(
            "completed"
            if state.is_completed and not issues
            else state.current_step.value
        ),
        completed_steps=[step.value for step in state.completed_steps],
        skipped_steps=[step.value for step in state.skipped_steps],
        progress_percentage=state.get_progress_percentage(),
        remaining_steps=[step.value for step in state.get_remaining_steps()],
        step_details=state.step_details,
        required_setup_issues=[_issue_response(issue) for issue in issues],
    )


def _required_setup_http_error(
    error: RequiredSetupIncompleteError,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": str(error),
            "required_setup_issues": [
                _issue_response(issue).dict() for issue in error.issues
            ],
        },
    )
