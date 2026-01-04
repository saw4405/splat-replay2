"""DI Container: Adapter registration.

Phase 3 リファクタリング - インフラアダプタの登録を分離。
"""

from __future__ import annotations

from typing import Optional, cast

import punq
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    AuthenticatedClientPort,
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CapturePort,
    DomainEventPublisher,
    EventBusPort,
    EventPublisher,
    FramePublisher,
    ImageSelector,
    PowerPort,
    RecorderWithTranscriptionPort,
    SettingsRepositoryPort,
    SpeechTranscriberPort,
    SubtitleEditorPort,
    SystemCommandPort,
    TextToSpeechPort,
    UploadPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
    VideoRecorderPort,
)
from splat_replay.domain.config import VideoStorageSettings
from splat_replay.domain.models import Frame
from splat_replay.domain.ports import ImageMatcherPort, OCRPort
from splat_replay.domain.ports.image_editor import (
    ImageEditorFactory,
    ImageEditorPort,
)
from splat_replay.domain.repositories import SetupStateRepository
from splat_replay.infrastructure import (
    CaptureDeviceChecker,
    CaptureDeviceEnumerator,
    EventBusPortAdapter,
    EventPublisherAdapter,
    FFmpegProcessor,
    FileVideoAssetRepository,
    FramePublisherAdapter,
    GoogleTextToSpeech,
    GuiRuntimePortAdapter,
    ImageDrawer,
    IntegratedSpeechRecognizer,
    MatcherRegistry,
    NDICapture,
    OBSRecorderController,
    RecorderWithTranscription,
    SetupStateFileAdapter,
    SpeechTranscriber,
    SubtitleEditor,
    SystemCommandAdapter,
    SystemPower,
    TesseractOCR,
    TomlSettingsRepository,
    YouTubeClient,
)
from splat_replay.infrastructure.filesystem import paths
from splat_replay.infrastructure.runtime import AppRuntime


def register_adapters(container: punq.Container) -> None:
    """アダプターを DI コンテナに登録する。"""
    container.register(CaptureDevicePort, CaptureDeviceChecker)
    container.register(CaptureDeviceEnumeratorPort, CaptureDeviceEnumerator)
    # ========== DEBUG/FIX START ==========
    # 修正: CapturePort をシングルトンとして登録
    # 理由: setup() で初期化された NDI 接続を、FrameCaptureProducer でも使用する必要がある
    # 元のコード: container.register(CapturePort, NDICapture)
    container.register(CapturePort, NDICapture, scope=punq.Scope.singleton)
    # ========== DEBUG/FIX END ==========
    # Single OBS controller prevents duplicate event callbacks/logs.
    container.register(
        VideoRecorderPort, OBSRecorderController, scope=punq.Scope.singleton
    )
    container.register(VideoEditorPort, FFmpegProcessor)

    # ImageEditorFactory: Frameごとに新しいImageEditorを生成するFactory関数
    from splat_replay.infrastructure.adapters.image.image_editor import (
        ImageEditor,
    )

    def _image_editor_factory(frame: Frame) -> ImageEditorPort:
        return ImageEditor(frame)

    container.register(ImageEditorFactory, instance=_image_editor_factory)

    container.register(PowerPort, SystemPower)
    container.register(OCRPort, TesseractOCR)
    container.register(UploadPort, YouTubeClient)
    container.register(AuthenticatedClientPort, YouTubeClient)
    container.register(SystemCommandPort, SystemCommandAdapter)

    # SetupStateRepository の登録
    def _setup_state_repo_factory() -> SetupStateRepository:
        state_file = paths.CONFIG_DIR / "installation_state.toml"
        return SetupStateFileAdapter(state_file)

    container.register(SetupStateRepository, factory=_setup_state_repo_factory)

    # EventPublisherAdapter には AppRuntime の event_bus を注入する
    def _event_publisher_factory() -> EventPublisher:
        rt = container.resolve(AppRuntime)
        return cast(EventPublisher, EventPublisherAdapter(rt.event_bus))

    container.register(EventPublisher, factory=_event_publisher_factory)

    # EventBusPortAdapter には AppRuntime の event_bus を注入する
    def _event_bus_port_factory() -> EventBusPort:
        rt = container.resolve(AppRuntime)
        return cast(EventBusPort, EventBusPortAdapter(rt.event_bus))

    container.register(EventBusPort, factory=_event_bus_port_factory)

    # DomainEventPublisher には AppRuntime の event_bus を注入する
    def _domain_event_publisher_factory() -> DomainEventPublisher:
        rt = container.resolve(AppRuntime)
        return cast(DomainEventPublisher, EventBusPortAdapter(rt.event_bus))

    container.register(
        DomainEventPublisher, factory=_domain_event_publisher_factory
    )

    def _frame_publisher_factory() -> FramePublisher:
        rt = container.resolve(AppRuntime)
        return cast(FramePublisher, FramePublisherAdapter(rt.frame_hub))

    container.register(FramePublisher, factory=_frame_publisher_factory)
    container.register(IntegratedSpeechRecognizer, IntegratedSpeechRecognizer)

    # Aggregated GUI runtime ports (command/event/frame)
    def _gui_runtime_factory() -> GuiRuntimePortAdapter:
        rt = container.resolve(AppRuntime)
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
    try:
        container.register(TextToSpeechPort, GoogleTextToSpeech)
        container.resolve(TextToSpeechPort)
    except Exception:
        container.register(TextToSpeechPort, factory=lambda: None)
    container.register(
        SettingsRepositoryPort, factory=lambda: TomlSettingsRepository()
    )

    # VideoAssetRepository は DomainEventPublisher を利用するため factory で注入
    def _video_asset_repo_factory() -> VideoAssetRepositoryPort:
        publisher = container.resolve(DomainEventPublisher)
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
