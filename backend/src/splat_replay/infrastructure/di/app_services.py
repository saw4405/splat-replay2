"""DI Container: Application services registration.

Phase 3 リファクタリング - アプリケーションサービスの登録を分離。
"""

from __future__ import annotations

import punq
from punq import Container

from splat_replay.application.interfaces import (
    CapturePort,
    DomainEventPublisher,
    EventPublisher,
    FramePublisher,
    LoggerPort,
    RecorderWithTranscriptionPort,
    VideoAssetRepositoryPort,
)
from splat_replay.application.services import (
    AutoEditor,
    AutoRecorder,
    AutoUploader,
    DeviceChecker,
    ErrorHandler,
    PowerManager,
    ProgressReporter,
    ProgressEventStore,
    RecordingPreparationService,
    SettingsService,
    SetupService,
    SystemCheckService,
    SystemSetupService,
)
from splat_replay.application.services.checkers import (
    FFMPEGChecker,
    OBSChecker,
    TesseractChecker,
)
from splat_replay.application.services.common.queries import AssetQueryService
from splat_replay.application.services.errors.error_logger import ErrorLogger
from splat_replay.application.services.process.auto_process_service import (
    AutoProcessService,
)
from splat_replay.application.use_cases.auto_recording_use_case import (
    AutoRecordingUseCase,
)
from splat_replay.domain.services import FrameAnalyzer
from splat_replay.domain.services.state_machine import StateMachine


def register_app_services(container: Container) -> None:
    """アプリケーションサービスを DI コンテナに登録する。"""
    container.register(DeviceChecker, DeviceChecker)
    container.register(
        RecordingPreparationService, RecordingPreparationService
    )

    # AutoRecorder に DomainEventPublisher を注入
    def auto_recorder_factory() -> AutoRecorder:
        state_machine = container.resolve(StateMachine)
        capture = container.resolve(CapturePort)
        analyzer = container.resolve(FrameAnalyzer)
        recorder = container.resolve(RecorderWithTranscriptionPort)
        asset_repository = container.resolve(VideoAssetRepositoryPort)
        logger = container.resolve(LoggerPort)
        publisher = container.resolve(EventPublisher)
        frame_publisher = container.resolve(FramePublisher)
        domain_publisher = container.resolve(DomainEventPublisher)

        return AutoRecorder(
            state_machine=state_machine,
            capture=capture,
            analyzer=analyzer,
            recorder=recorder,
            asset_repository=asset_repository,
            logger=logger,
            publisher=publisher,
            frame_publisher=frame_publisher,
            domain_publisher=domain_publisher,
        )

    container.register(AutoRecorder, factory=auto_recorder_factory)

    # AutoRecordingUseCase の登録
    def auto_recording_use_case_factory() -> AutoRecordingUseCase:
        auto_recorder = container.resolve(AutoRecorder)
        capture = container.resolve(CapturePort)
        logger = container.resolve(LoggerPort)

        return AutoRecordingUseCase(
            session_service=auto_recorder.session_service,
            frame_processor=auto_recorder.frame_processor,
            phase_handlers=auto_recorder.phase_handlers,
            context=auto_recorder.context,
            capture=capture,
            capture_producer=auto_recorder.capture_producer,
            publisher_worker=auto_recorder.publisher_worker,
            logger=logger,
        )

    container.register(
        AutoRecordingUseCase,
        factory=auto_recording_use_case_factory,
        scope=punq.Scope.singleton,
    )

    container.register(
        ProgressEventStore, ProgressEventStore, scope=punq.Scope.singleton
    )

    def progress_reporter_factory() -> ProgressReporter:
        publisher = container.resolve(EventPublisher)
        logger = container.resolve(LoggerPort)
        progress_store = container.resolve(ProgressEventStore)
        progress = ProgressReporter(publisher, logger)
        progress.add_listener(progress_store.record)
        return progress

    # ProgressReporter を生成
    container.register(
        ProgressReporter,
        factory=progress_reporter_factory,
    )

    container.register(AutoEditor, AutoEditor)
    container.register(AutoUploader, AutoUploader)
    container.register(AutoProcessService, AutoProcessService)
    container.register(PowerManager, PowerManager)
    container.register(AssetQueryService, AssetQueryService)
    container.register(SettingsService, SettingsService)
    container.register(SetupService, SetupService)
    container.register(SystemSetupService, SystemSetupService)
    container.register(ErrorLogger, ErrorLogger)

    # ErrorHandler - Optional引数のため factory で登録
    def error_handler_factory() -> ErrorHandler:
        logger = container.resolve(LoggerPort)
        error_logger = container.resolve(ErrorLogger)
        return ErrorHandler(logger=logger, error_logger=error_logger)

    container.register(ErrorHandler, factory=error_handler_factory)

    # Software checkers
    container.register(OBSChecker, OBSChecker)
    container.register(FFMPEGChecker, FFMPEGChecker)
    container.register(TesseractChecker, TesseractChecker)

    # SystemCheckService - Protocol型の依存を明示的に注入
    def system_check_service_factory() -> SystemCheckService:
        from splat_replay.application.interfaces import (
            EnvironmentPort,
            FileSystemPort,
            PathsPort,
        )

        obs_checker = container.resolve(OBSChecker)
        ffmpeg_checker = container.resolve(FFMPEGChecker)
        tesseract_checker = container.resolve(TesseractChecker)
        paths = container.resolve(PathsPort)
        file_system = container.resolve(FileSystemPort)
        environment = container.resolve(EnvironmentPort)
        logger = container.resolve(LoggerPort)

        return SystemCheckService(
            obs_checker=obs_checker,
            ffmpeg_checker=ffmpeg_checker,
            tesseract_checker=tesseract_checker,
            paths=paths,
            file_system=file_system,
            environment=environment,
            logger=logger,
        )

    container.register(
        SystemCheckService, factory=system_check_service_factory
    )
