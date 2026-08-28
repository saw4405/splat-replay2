"""DI Container: Adapter registration.

Phase 3 リファクタリング - インフラアダプタの登録を分離。
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional, cast

import punq
from splat_replay.application.interfaces import (
    AuthenticatedClientPort,
    BattleHistoryRepositoryPort,
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CaptureDeviceSettingsView,
    CapturePort,
    ClockPort,
    DomainEventPublisher,
    EnvironmentPort,
    EventBusPort,
    EventPublisher,
    FramePublisher,
    FramePreviewPort,
    ImageSelector,
    LoggerPort,
    MicrophoneEnumeratorPort,
    OBSSettingsView,
    PowerPort,
    RecorderWithTranscriptionPort,
    ReplayBootstrapResolverPort,
    SettingsRepositoryPort,
    SpeechTranscriberPort,
    SubtitleEditorPort,
    SystemCommandPort,
    TextToSpeechPort,
    UploadPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
    VideoRecorderPort,
    WeaponRecognitionPort,
    XPDetectionDiagnosticsPort,
)
from splat_replay.domain.config import VideoEditSettings, VideoStorageSettings
from splat_replay.domain.models import Frame
from splat_replay.domain.ports import (
    BattleMedalRecognizerPort,
    ImageMatcherPort,
    OCRPort,
)
from splat_replay.domain.ports.image_editor import (
    ImageEditorFactory,
    ImageEditorPort,
)
from splat_replay.domain.repositories import SetupStateRepository
from splat_replay.infrastructure import (
    AdaptiveCapture,
    AdaptiveCaptureDeviceChecker,
    AdaptiveVideoRecorder,
    EventBusPortAdapter,
    EventPublisherAdapter,
    FFmpegProcessor,
    FileBattleHistoryRepository,
    FileVideoAssetRepository,
    FramePublisherAdapter,
    GuiRuntimePortAdapter,
    ImageDrawer,
    MatcherRegistry,
    RecorderWithTranscription,
    ReplayOCRAdapter,
    ReplayWeaponRecognitionAdapter,
    SetupStateFileAdapter,
    SubtitleEditor,
    SystemCommandAdapter,
    TomlSettingsRepository,
    YouTubeClient,
)
from splat_replay.infrastructure.adapters.system.capture_clock import (
    CaptureClock,
)
from splat_replay.infrastructure.adapters.system.replay_runtime import (
    ReplayCaptureDeviceEnumerator,
    ReplayMicrophoneEnumerator,
    ReplayPower,
)
from splat_replay.infrastructure.adapters.diagnostics import (
    FileXPDetectionDiagnostics,
)
from splat_replay.infrastructure.adapters.upload import NoOpUploadPort
from splat_replay.infrastructure.config import load_settings_from_toml
from splat_replay.infrastructure.di.runtime_profile import RuntimeProfile
from splat_replay.infrastructure.filesystem import paths
from splat_replay.infrastructure.runtime import AppRuntime
from splat_replay.infrastructure.test_input import (
    ConfiguredReplayBootstrapResolver,
)
from structlog.stdlib import BoundLogger


def _is_e2e_noop_upload_enabled(environment: EnvironmentPort) -> bool:
    return environment.get("SPLAT_REPLAY_E2E_NOOP_UPLOAD", "0") == "1"


def register_adapters(
    container: punq.Container,
    profile: RuntimeProfile = RuntimeProfile.LIVE,
) -> None:
    """アダプターを DI コンテナに登録する。"""
    if profile is RuntimeProfile.REPLAY:

        def _replay_capture_device_factory() -> CaptureDevicePort:
            return AdaptiveCaptureDeviceChecker(
                cast(
                    CaptureDeviceSettingsView,
                    container.resolve(CaptureDeviceSettingsView),
                ),
                cast(BoundLogger, container.resolve(BoundLogger)),
                live_checker_factory=None,
            )

        def _replay_capture_factory() -> CapturePort:
            return AdaptiveCapture(
                cast(BoundLogger, container.resolve(BoundLogger)),
                live_capture_factory=None,
            )

        def _replay_recorder_factory() -> VideoRecorderPort:
            return AdaptiveVideoRecorder(
                cast(OBSSettingsView, container.resolve(OBSSettingsView)),
                cast(
                    VideoStorageSettings,
                    container.resolve(VideoStorageSettings),
                ),
                cast(BoundLogger, container.resolve(BoundLogger)),
                live_recorder_factory=None,
            )

        container.register(
            CaptureDevicePort, factory=_replay_capture_device_factory
        )
        container.register(
            CaptureDeviceEnumeratorPort, ReplayCaptureDeviceEnumerator
        )
        container.register(
            MicrophoneEnumeratorPort, ReplayMicrophoneEnumerator
        )
        container.register(
            CapturePort,
            factory=_replay_capture_factory,
            scope=punq.Scope.singleton,
        )
        container.register(
            VideoRecorderPort,
            factory=_replay_recorder_factory,
            scope=punq.Scope.singleton,
        )
        container.register(PowerPort, ReplayPower)
    else:
        from splat_replay.infrastructure.adapters.capture.capture_device_checker import (
            CaptureDeviceEnumerator,
        )
        from splat_replay.infrastructure.adapters.system.system_power import (
            SystemPower,
        )

        container.register(CaptureDevicePort, AdaptiveCaptureDeviceChecker)
        container.register(
            CaptureDeviceEnumeratorPort, CaptureDeviceEnumerator
        )

        def _microphone_enumerator_factory() -> MicrophoneEnumeratorPort:
            from splat_replay.infrastructure.adapters.audio.microphone_enumerator import (
                MicrophoneEnumerator,
            )

            return MicrophoneEnumerator(
                cast(BoundLogger, container.resolve(BoundLogger))
            )

        container.register(
            MicrophoneEnumeratorPort, factory=_microphone_enumerator_factory
        )
        container.register(
            CapturePort, AdaptiveCapture, scope=punq.Scope.singleton
        )
        container.register(
            VideoRecorderPort,
            AdaptiveVideoRecorder,
            scope=punq.Scope.singleton,
        )
        container.register(PowerPort, SystemPower)

    container.register(
        ClockPort,
        factory=lambda: CaptureClock(container.resolve(CapturePort)),
        scope=punq.Scope.singleton,
    )
    container.register(
        ReplayBootstrapResolverPort,
        ConfiguredReplayBootstrapResolver,
        scope=punq.Scope.singleton,
    )
    container.register(VideoEditorPort, FFmpegProcessor)
    container.register(
        FramePreviewPort,
        FFmpegProcessor,
        scope=punq.Scope.singleton,
    )

    # ImageEditorFactory: Frameごとに新しいImageEditorを生成するFactory関数
    from splat_replay.infrastructure.adapters.image.image_editor import (
        ImageEditor,
    )

    def _image_editor_factory(frame: Frame) -> ImageEditorPort:
        return ImageEditor(frame)

    container.register(ImageEditorFactory, instance=_image_editor_factory)

    if profile is RuntimeProfile.REPLAY:
        container.register(OCRPort, ReplayOCRAdapter)
    else:
        from splat_replay.infrastructure import TesseractOCR

        container.register(OCRPort, TesseractOCR)
    if profile is RuntimeProfile.REPLAY:
        from splat_replay.infrastructure.adapters.medal_detection.replay_recognizer import (
            ReplayBattleMedalRecognizerAdapter,
        )

        container.register(
            BattleMedalRecognizerPort,
            ReplayBattleMedalRecognizerAdapter,
        )
    else:
        from splat_replay.infrastructure.adapters.medal_detection.recognizer import (
            BattleMedalRecognizerAdapter,
        )

        container.register(
            BattleMedalRecognizerPort, BattleMedalRecognizerAdapter
        )
    environment = container.resolve(EnvironmentPort)
    if _is_e2e_noop_upload_enabled(environment):
        container.register(UploadPort, NoOpUploadPort)
    else:
        container.register(UploadPort, YouTubeClient)
    container.register(AuthenticatedClientPort, YouTubeClient)
    container.register(SystemCommandPort, SystemCommandAdapter)

    # SetupStateRepository の登録
    def _setup_state_repo_factory() -> SetupStateRepository:
        state_file = paths.SETTINGS_FILE.parent / "installation_state.toml"
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

    # Aggregated GUI runtime ports (command/event/frame)
    def _gui_runtime_factory() -> GuiRuntimePortAdapter:
        rt = container.resolve(AppRuntime)
        return GuiRuntimePortAdapter(rt)

    container.register(GuiRuntimePortAdapter, factory=_gui_runtime_factory)
    container.register(
        SpeechTranscriberPort, factory=lambda: _build_speech_transcriber()[0]
    )
    container.register(ImageMatcherPort, MatcherRegistry)
    container.register(SubtitleEditorPort, SubtitleEditor)
    container.register(
        XPDetectionDiagnosticsPort,
        factory=lambda: FileXPDetectionDiagnostics(
            logger=cast(LoggerPort, container.resolve(LoggerPort))
        ),
        scope=punq.Scope.singleton,
    )
    container.register(
        ImageSelector, instance=ImageDrawer.select_brightest_image
    )
    if profile is RuntimeProfile.REPLAY:
        container.register(
            WeaponRecognitionPort,
            ReplayWeaponRecognitionAdapter,
            scope=punq.Scope.singleton,
        )
    else:
        from splat_replay.infrastructure import WeaponRecognitionAdapter

        container.register(
            WeaponRecognitionPort,
            WeaponRecognitionAdapter,
            scope=punq.Scope.singleton,
        )

    def _text_to_speech_factory() -> TextToSpeechPort | None:
        try:
            from splat_replay.infrastructure.adapters.audio.google_text_to_speech import (
                GoogleTextToSpeech,
            )

            return GoogleTextToSpeech(
                cast(VideoEditSettings, container.resolve(VideoEditSettings)),
                cast(BoundLogger, container.resolve(BoundLogger)),
            )
        except Exception:
            return None

    container.register(TextToSpeechPort, factory=_text_to_speech_factory)

    def _settings_repository_factory() -> SettingsRepositoryPort:
        device_enumerator = container.resolve(CaptureDeviceEnumeratorPort)
        microphone_enumerator = container.resolve(MicrophoneEnumeratorPort)
        return TomlSettingsRepository(
            device_enumerator=device_enumerator,
            microphone_enumerator=microphone_enumerator,
        )

    container.register(
        SettingsRepositoryPort, factory=_settings_repository_factory
    )

    def _battle_history_repo_factory() -> BattleHistoryRepositoryPort:
        settings = cast(
            VideoStorageSettings, container.resolve(VideoStorageSettings)
        )
        return FileBattleHistoryRepository(
            settings,
            cast(BoundLogger, container.resolve(BoundLogger)),
        )

    container.register(
        BattleHistoryRepositoryPort,
        factory=_battle_history_repo_factory,
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

    def _build_speech_transcriber() -> tuple[
        Optional[SpeechTranscriberPort], str
    ]:
        logger = cast(BoundLogger, container.resolve(BoundLogger))
        event_publisher = cast(
            DomainEventPublisher, container.resolve(DomainEventPublisher)
        )
        settings = load_settings_from_toml()
        speech_settings = settings.speech_transcriber
        fingerprint_payload = json.dumps(
            {
                "enabled": speech_settings.enabled,
                "mic_device_name": speech_settings.mic_device_name,
                "groq_api_key": speech_settings.groq_api_key.get_secret_value(),
                "language": speech_settings.language,
                "custom_dictionary": speech_settings.custom_dictionary,
                "vad_aggressiveness": speech_settings.vad_aggressiveness,
                "vad_min_speech_frames": speech_settings.vad_min_speech_frames,
                "vad_min_speech_ratio": speech_settings.vad_min_speech_ratio,
                "groq_model": speech_settings.groq_model,
                "integrator_model": speech_settings.integrator_model,
                "phrase_time_limit": speech_settings.phrase_time_limit,
                "energy_threshold": speech_settings.energy_threshold,
                "no_speech_prob_threshold": speech_settings.no_speech_prob_threshold,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(
            fingerprint_payload.encode("utf-8")
        ).hexdigest()
        if not speech_settings.enabled:
            logger.info("文字起こしを無効化します", reason="無効設定")
            return None, fingerprint
        if not speech_settings.mic_device_name.strip():
            logger.info("文字起こしを無効化します", reason="マイク名が未設定")
            return None, fingerprint
        try:
            from splat_replay.infrastructure.adapters.audio.integrated_speech_recognition import (
                IntegratedSpeechRecognizer,
            )
            from splat_replay.infrastructure.adapters.audio.speech_transcriber import (
                SpeechTranscriber,
            )

            recognizer = IntegratedSpeechRecognizer(speech_settings, logger)
            return (
                SpeechTranscriber(
                    speech_settings, recognizer, logger, event_publisher
                ),
                fingerprint,
            )
        except Exception as exc:
            logger.warning("文字起こしの初期化に失敗しました", error=str(exc))
            return None, fingerprint

    recorder_with_transcription_instance = RecorderWithTranscription(
        cast(VideoRecorderPort, container.resolve(VideoRecorderPort)),
        None,
        cast(
            VideoAssetRepositoryPort,
            container.resolve(VideoAssetRepositoryPort),
        ),
        cast(BoundLogger, container.resolve(BoundLogger)),
        transcriber_factory=_build_speech_transcriber,
    )
    container.register(
        RecorderWithTranscriptionPort,
        instance=recorder_with_transcription_instance,
    )
