"""Web application composition root."""

from __future__ import annotations

import punq
from fastapi import FastAPI
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import EventBusPort
from splat_replay.application.services import (
    AutoRecorder,
    DeviceChecker,
    ErrorHandler,
    RecordingPreparationService,
    SetupService,
    SystemCheckService,
    SystemSetupService,
)
from splat_replay.application.services.common.settings_service import (
    SettingsService,
)
from splat_replay.application.use_cases import (
    AutoRecordingUseCase,
    UploadUseCase,
)
from splat_replay.application.use_cases.assets import (
    DeleteEditedVideoUseCase,
    DeleteRecordedVideoUseCase,
    GetEditUploadStatusUseCase,
    ListEditedVideosUseCase,
    ListRecordedVideosUseCase,
    StartEditUploadUseCase,
)
from splat_replay.application.use_cases.metadata import (
    GetRecordedSubtitleStructuredUseCase,
    UpdateRecordedMetadataUseCase,
    UpdateRecordedSubtitleStructuredUseCase,
)
from splat_replay.domain.config import AppSettings
from splat_replay.infrastructure.di import configure_container, resolve
from splat_replay.infrastructure.filesystem import PROJECT_ROOT, RUNTIME_ROOT
from splat_replay.interface.web.app_factory import create_app as create_web_app
from splat_replay.interface.web.server import WebAPIServer


def build_web_api_server(container: punq.Container) -> WebAPIServer:
    """Resolve dependencies and assemble WebAPIServer."""
    auto_recorder = resolve(container, AutoRecorder)
    device_checker = resolve(container, DeviceChecker)
    recording_preparation_service = resolve(
        container, RecordingPreparationService
    )
    settings_service = resolve(container, SettingsService)
    event_bus_port = resolve(container, EventBusPort)
    upload_use_case = resolve(container, UploadUseCase)

    def auto_recording_use_case_factory() -> AutoRecordingUseCase:
        return resolve(container, AutoRecordingUseCase)

    setup_service = resolve(container, SetupService)
    system_check_service = resolve(container, SystemCheckService)
    system_setup_service = resolve(container, SystemSetupService)
    error_handler = resolve(container, ErrorHandler)
    logger = resolve(container, BoundLogger)

    list_recorded_videos_uc = resolve(container, ListRecordedVideosUseCase)
    delete_recorded_video_uc = resolve(container, DeleteRecordedVideoUseCase)
    list_edited_videos_uc = resolve(container, ListEditedVideosUseCase)
    delete_edited_video_uc = resolve(container, DeleteEditedVideoUseCase)
    get_edit_upload_status_uc = resolve(container, GetEditUploadStatusUseCase)
    start_edit_upload_uc = resolve(container, StartEditUploadUseCase)
    update_recorded_metadata_uc = resolve(
        container, UpdateRecordedMetadataUseCase
    )
    get_recorded_subtitle_structured_uc = resolve(
        container, GetRecordedSubtitleStructuredUseCase
    )
    update_recorded_subtitle_structured_uc = resolve(
        container, UpdateRecordedSubtitleStructuredUseCase
    )

    # 録画ファイル保存先を取得
    app_settings = resolve(container, AppSettings)
    base_dir = app_settings.storage.base_dir

    return WebAPIServer(
        settings_service=settings_service,
        setup_service=setup_service,
        system_check_service=system_check_service,
        system_setup_service=system_setup_service,
        error_handler=error_handler,
        logger=logger,
        device_checker=device_checker,
        recording_preparation_service=recording_preparation_service,
        upload_use_case=upload_use_case,
        auto_recording_use_case_factory=auto_recording_use_case_factory,
        auto_recorder=auto_recorder,
        event_bus=event_bus_port,
        project_root=PROJECT_ROOT,
        runtime_root=RUNTIME_ROOT,
        base_dir=base_dir,
        # Assets Use Cases
        list_recorded_videos_uc=list_recorded_videos_uc,
        delete_recorded_video_uc=delete_recorded_video_uc,
        list_edited_videos_uc=list_edited_videos_uc,
        delete_edited_video_uc=delete_edited_video_uc,
        get_edit_upload_status_uc=get_edit_upload_status_uc,
        start_edit_upload_uc=start_edit_upload_uc,
        # Metadata Use Cases
        update_recorded_metadata_uc=update_recorded_metadata_uc,
        get_recorded_subtitle_structured_uc=get_recorded_subtitle_structured_uc,
        update_recorded_subtitle_structured_uc=update_recorded_subtitle_structured_uc,
    )


def create_app(container: punq.Container | None = None) -> FastAPI:
    """Create the FastAPI app with resolved dependencies."""
    if container is None:
        container = configure_container()
    server = build_web_api_server(container)
    return create_web_app(server)


# Expose a factory for uvicorn's --factory mode.
app = create_app

__all__ = ["app", "create_app", "build_web_api_server"]
