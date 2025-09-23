"""DI コンテナ設定モジュール。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, TypeVar, cast

import punq
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    AuthenticatedClientPort,
    CaptureDevicePort,
    CapturePort,
    EventPublisher,
    FramePublisher,
    ImageSelector,
    PowerPort,
    RecorderWithTranscriptionPort,
    SpeechTranscriberPort,
    SubtitleEditorPort,
    UploadPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
    VideoRecorderPort,
)
from splat_replay.application.services import (
    AutoEditor,
    AutoRecorder,
    AutoUploader,
    DeviceChecker,
    PowerManager,
    ProgressReporter,
)
from splat_replay.application.services.queries import AssetQueryService
from splat_replay.application.use_cases import AutoUseCase, UploadUseCase
from splat_replay.domain.services import (
    BattleFrameAnalyzer,
    FrameAnalyzer,
    ImageEditorFactory,
    ImageMatcherPort,
    OCRPort,
    SalmonFrameAnalyzer,
    StateMachine,
)
from splat_replay.infrastructure import (
    Capture,
    CaptureDeviceChecker,
    EventPublisherAdapter,
    FFmpegProcessor,
    FileVideoAssetRepository,
    FramePublisherAdapter,
    GuiRuntimePortAdapter,
    ImageDrawer,
    ImageEditor,
    IntegratedSpeechRecognizer,
    MatcherRegistry,
    OBSController,
    RecorderWithTranscription,
    SpeechTranscriber,
    SubtitleEditor,
    SystemPower,
    TesseractOCR,
    YouTubeClient,
)
from splat_replay.infrastructure.runtime.runtime import AppRuntime
from splat_replay.shared import paths
from splat_replay.shared.config import (
    AppSettings,
    BehaviorSettings,
    CaptureDeviceSettings,
    ImageMatchingSettings,
    OBSSettings,
    RecordSettings,
    SpeechTranscriberSettings,
    UploadSettings,
    VideoEditSettings,
    VideoStorageSettings,
)
from splat_replay.shared.logger import get_logger


def register_config(container: punq.Container) -> AppSettings:
    """設定を DI コンテナに登録する。"""
    settings = AppSettings.load_from_toml()
    container.register(BehaviorSettings, instance=settings.behavior)
    container.register(CaptureDeviceSettings, instance=settings.capture_device)
    container.register(OBSSettings, instance=settings.obs)
    container.register(RecordSettings, instance=settings.record)
    container.register(
        SpeechTranscriberSettings, instance=settings.speech_transcriber
    )
    container.register(VideoStorageSettings, instance=settings.storage)
    container.register(VideoEditSettings, instance=settings.video_edit)
    container.register(UploadSettings, instance=settings.upload)
    return settings


def register_image_matching_settings(
    container: punq.Container, path: Path
) -> ImageMatchingSettings:
    """画像マッチング設定を DI コンテナに登録する。"""
    if not path.exists():
        raise FileNotFoundError(
            f"画像マッチング設定ファイルが見つかりません: {path}"
        )
    image_settings = ImageMatchingSettings.load_from_yaml(path)
    container.register(ImageMatchingSettings, instance=image_settings)
    return image_settings


def register_adapters(container: punq.Container) -> None:
    """アダプターを DI コンテナに登録する。"""
    container.register(CaptureDevicePort, CaptureDeviceChecker)
    container.register(CapturePort, Capture)
    container.register(VideoRecorderPort, OBSController)
    container.register(VideoEditorPort, FFmpegProcessor)
    container.register(ImageEditorFactory, instance=ImageEditor)
    container.register(PowerPort, SystemPower)
    container.register(OCRPort, TesseractOCR)
    container.register(UploadPort, YouTubeClient)
    container.register(AuthenticatedClientPort, YouTubeClient)

    # EventPublisherAdapter には AppRuntime の event_bus を注入する
    def _event_publisher_factory() -> EventPublisher:
        rt = cast(AppRuntime, resolve(container, AppRuntime))
        return cast(EventPublisher, EventPublisherAdapter(rt.event_bus))

    container.register(EventPublisher, factory=_event_publisher_factory)

    def _frame_publisher_factory() -> FramePublisher:
        rt = cast(AppRuntime, resolve(container, AppRuntime))
        return cast(FramePublisher, FramePublisherAdapter(rt.frame_hub))

    container.register(FramePublisher, factory=_frame_publisher_factory)
    container.register(IntegratedSpeechRecognizer, IntegratedSpeechRecognizer)

    # Aggregated GUI runtime ports (command/event/frame)
    def _gui_runtime_factory() -> GuiRuntimePortAdapter:
        rt = cast(AppRuntime, resolve(container, AppRuntime))
        return GuiRuntimePortAdapter(rt)

    container.register(GuiRuntimePortAdapter, factory=_gui_runtime_factory)
    try:
        container.register(SpeechTranscriberPort, SpeechTranscriber)
        container.resolve(SpeechTranscriberPort)
    except Exception:
        container.register(SpeechTranscriberPort, factory=lambda: None)
    container.register(ImageMatcherPort, MatcherRegistry)
    container.register(SubtitleEditorPort, SubtitleEditor)
    container.register(
        ImageSelector, instance=ImageDrawer.select_brightest_image
    )

    # VideoAssetRepository は EventPublisher を利用するため factory で注入
    def _video_asset_repo_factory() -> VideoAssetRepositoryPort:
        publisher = cast(EventPublisher, resolve(container, EventPublisher))
        return FileVideoAssetRepository(
            cast(
                VideoStorageSettings, container.resolve(VideoStorageSettings)
            ),
            cast(BoundLogger, container.resolve(BoundLogger)),
            publisher,
        )

    container.register(
        VideoAssetRepositoryPort, factory=_video_asset_repo_factory
    )
    recorder_with_transcription_instance = RecorderWithTranscription(
        cast(VideoRecorderPort, container.resolve(VideoRecorderPort)),
        cast(
            Optional[SpeechTranscriberPort],
            container.resolve(SpeechTranscriberPort),
        ),
        cast(
            VideoAssetRepositoryPort,
            container.resolve(VideoAssetRepositoryPort),
        ),
        cast(BoundLogger, container.resolve(BoundLogger)),
    )
    container.register(
        RecorderWithTranscriptionPort,
        instance=recorder_with_transcription_instance,
    )


def register_domain_services(container: punq.Container) -> None:
    """ドメインサービスを DI コンテナに登録する。"""
    container.register(FrameAnalyzer, FrameAnalyzer)
    container.register(BattleFrameAnalyzer, BattleFrameAnalyzer)
    container.register(SalmonFrameAnalyzer, SalmonFrameAnalyzer)


def register_app_services(container: punq.Container) -> None:
    """アプリケーションサービスを DI コンテナに登録する。"""
    container.register(DeviceChecker, DeviceChecker)
    # Inject runtime-aware services
    container.register(AutoRecorder, AutoRecorder)
    container.register(ProgressReporter, ProgressReporter)
    container.register(AutoEditor, AutoEditor)
    container.register(AutoUploader, AutoUploader)
    container.register(PowerManager, PowerManager)
    container.register(AssetQueryService, AssetQueryService)


def register_app_usecases(container: punq.Container) -> None:
    """アプリケーションのユースケースを DI コンテナに登録する。"""
    container.register(AutoUseCase, AutoUseCase)
    container.register(UploadUseCase, UploadUseCase)


def configure_container() -> punq.Container:
    """アプリで利用する依存関係を登録する。"""
    container = punq.Container()

    logger = get_logger()
    container.register(BoundLogger, instance=logger)
    state_machine = StateMachine(logger)
    container.register(StateMachine, instance=state_machine)

    # Runtime (async loop & buses)
    runtime = AppRuntime()
    runtime.start()
    container.register(AppRuntime, instance=runtime)

    register_config(container)
    register_image_matching_settings(container, paths.IMAGE_MATCHING_FILE)
    register_adapters(container)
    register_domain_services(container)
    register_app_services(container)
    register_app_usecases(container)

    try:
        ar = cast(AutoRecorder, resolve(container, AutoRecorder))
        rt = cast(AppRuntime, resolve(container, AppRuntime))
        handlers = ar.command_handlers()
        for name, handler in handlers.items():
            rt.command_bus.register(name, handler)
    except Exception:
        pass

    # Register asset query commands
    try:
        aq = cast(AssetQueryService, resolve(container, AssetQueryService))
        rt = cast(AppRuntime, resolve(container, AppRuntime))
        for name, handler in aq.command_handlers().items():
            rt.command_bus.register(name, handler)
    except Exception:
        pass

    return container


T = TypeVar("T")


def resolve(container: punq.Container, cls: object) -> Any:
    """DI コンテナから依存を解決する"""
    return container.resolve(cls)
