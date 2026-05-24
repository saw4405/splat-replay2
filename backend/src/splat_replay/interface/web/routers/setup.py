"""セットアップAPIルーター (ファサード)。

責務：サブルーターの統合。個別のエンドポイントロジックは各サブモジュールに委譲。
"""

from __future__ import annotations

from fastapi import APIRouter
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

from .setup_config import create_setup_config_router
from .setup_navigation import create_setup_navigation_router
from .setup_system import create_setup_system_router

__all__ = ["create_setup_router"]


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
    """セットアップAPIルーターを作成する。"""
    router = APIRouter(prefix="/setup", tags=["setup"])

    router.include_router(
        create_setup_navigation_router(setup_service, error_handler, logger)
    )
    router.include_router(
        create_setup_system_router(
            system_check_service, system_setup_service, error_handler, logger
        )
    )
    router.include_router(
        create_setup_config_router(
            recording_preparation_service,
            device_checker,
            auto_uploader,
            error_handler,
            logger,
        )
    )

    return router
