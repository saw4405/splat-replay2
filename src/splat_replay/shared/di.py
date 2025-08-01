"""DI コンテナ設定モジュール。"""

from __future__ import annotations

from pathlib import Path

import punq
from structlog.stdlib import BoundLogger

from splat_replay.shared.logger import get_logger
from splat_replay.shared.config import (
    AppSettings,
    CaptureDeviceSettings,
    OBSSettings,
    RecordSettings,
    SpeechTranscriberSettings,
    VideoStorageSettings,
    VideoEditSettings,
    UploadSettings,
    PCSettings,
    ImageMatchingSettings,
)
from splat_replay.domain.services import (
    StateMachine,
    ImageMatcherPort,
    OCRPort,
    ImageEditorFactory,
    FrameAnalyzer,
    AnalyzerPlugin,
    BattleFrameAnalyzer,
    SalmonFrameAnalyzer,
)
from splat_replay.application.services import (
    EnvironmentInitializer,
    AutoRecorder,
    AutoEditor,
    AutoUploader,
    PowerManager,
)
from splat_replay.application.use_cases import AutoUseCase, UploadUseCase
from splat_replay.application.interfaces import (
    CaptureDevicePort,
    CapturePort,
    VideoRecorder,
    OBSControlPort,
    SpeechTranscriberPort,
    VideoAssetRepository,
    VideoEditorPort,
    SubtitleEditorPort,
    ImageSelector,
    UploadPort,
    PowerPort,
)
from splat_replay.infrastructure import (
    CaptureDeviceChecker,
    Capture,
    MatcherRegistry,
    FFmpegProcessor,
    FileVideoAssetRepository,
    OBSController,
    SystemPower,
    YouTubeClient,
    TesseractOCR,
    ImageEditor,
    SubtitleEditor,
    ImageDrawer,
    IntegratedSpeechRecognizer,
    SpeechTranscriber,
)


def register_config(container: punq.Container, path: Path) -> AppSettings:
    """設定を DI コンテナに登録する。"""
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
    settings = AppSettings.load_from_toml(path)
    container.register(CaptureDeviceSettings, instance=settings.capture_device)
    container.register(OBSSettings, instance=settings.obs)
    container.register(RecordSettings, instance=settings.record)
    container.register(
        SpeechTranscriberSettings, instance=settings.speech_transcriber
    )
    container.register(VideoStorageSettings, instance=settings.storage)
    container.register(VideoEditSettings, instance=settings.video_edit)
    container.register(UploadSettings, instance=settings.upload)
    container.register(PCSettings, instance=settings.pc)
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


def register_adapters(container: punq.Container):
    """アダプターを DI コンテナに登録する。"""
    container.register(CaptureDevicePort, CaptureDeviceChecker)
    container.register(CapturePort, Capture)
    container.register(VideoEditorPort, FFmpegProcessor)
    container.register(ImageEditorFactory, instance=ImageEditor)
    container.register(VideoRecorder, OBSController)
    container.register(OBSControlPort, OBSController)
    container.register(PowerPort, SystemPower)
    container.register(OCRPort, TesseractOCR)
    container.register(UploadPort, YouTubeClient)
    container.register(IntegratedSpeechRecognizer, IntegratedSpeechRecognizer)
    container.register(SpeechTranscriberPort, SpeechTranscriber)
    container.register(ImageMatcherPort, MatcherRegistry)
    container.register(SubtitleEditorPort, SubtitleEditor)
    container.register(
        ImageSelector, instance=ImageDrawer.select_brightest_image
    )
    container.register(VideoAssetRepository, FileVideoAssetRepository)


def register_domain_services(container: punq.Container):
    """ドメインサービスを DI コンテナに登録する。"""
    container.register(FrameAnalyzer, FrameAnalyzer)
    container.register(BattleFrameAnalyzer, BattleFrameAnalyzer)
    container.register(SalmonFrameAnalyzer, SalmonFrameAnalyzer)


def register_app_services(container: punq.Container):
    """アプリケーションサービスを DI コンテナに登録する。"""
    container.register(EnvironmentInitializer, EnvironmentInitializer)
    container.register(AutoRecorder, AutoRecorder)
    container.register(AutoEditor, AutoEditor)
    container.register(AutoUploader, AutoUploader)
    container.register(PowerManager, PowerManager)


def register_app_usecases(container: punq.Container):
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

    register_config(container, Path("config/settings.toml"))
    register_image_matching_settings(
        container, Path("config/image_matching.yaml")
    )
    register_adapters(container)
    register_domain_services(container)
    register_app_services(container)
    register_app_usecases(container)
    return container
