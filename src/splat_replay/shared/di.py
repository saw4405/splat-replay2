"""DI コンテナ設定モジュール。"""

from __future__ import annotations

from pathlib import Path
from pydantic import ValidationError

from splat_replay.shared.logger import get_logger

import punq

from splat_replay.application import (
    ProcessPostGameUseCase,
    RecordBattleUseCase,
    PauseRecordingUseCase,
    ResumeRecordingUseCase,
    StopRecordingUseCase,
    ShutdownPCUseCase,
    UploadVideoUseCase,
    InitializeEnvironmentUseCase,
    CheckInitializationUseCase,
    DaemonUseCase,
)
from splat_replay.infrastructure import (
    CaptureDeviceChecker,
    FFmpegProcessor,
    FileMetadataRepository,
    GroqClient,
    OBSController,
    SystemPower,
    YouTubeClient,
    FrameAnalyzer,
    AnalyzerPlugin,
    BattleFrameAnalyzer,
    SalmonFrameAnalyzer,
)
from splat_replay.domain.services import (
    VideoEditor,
    SpeechTranscriber,
    MetadataExtractor,
    StateMachine,
)
from splat_replay.domain.repositories.metadata_repo import MetadataRepository
from splat_replay.application.interfaces import (
    VideoRecorder,
    VideoEditorPort,
    UploadPort,
    PowerPort,
    FrameAnalyzerPort,
    SpeechTranscriberPort,
    MetadataExtractorPort,
    CaptureDevicePort,
    OBSControlPort,
)
from splat_replay.shared.config import (
    AppSettings,
    YouTubeSettings,
    VideoEditSettings,
    OBSSettings,
    ImageMatchingSettings,
)


def configure_container() -> punq.Container:
    """アプリで利用する依存関係を登録する。"""

    logger = get_logger()

    container = punq.Container()

    settings_path = Path("config/settings.toml")
    # settings.toml が存在する場合はそこから設定を読み込む
    if settings_path.exists():
        settings = AppSettings.load_from_toml(settings_path)
    else:
        settings = AppSettings()
    # 設定オブジェクトを登録
    container.register(AppSettings, instance=settings)
    container.register(YouTubeSettings, instance=settings.youtube)
    container.register(VideoEditSettings, instance=settings.video_edit)
    container.register(OBSSettings, instance=settings.obs)

    image_match_path = Path("config/image_matching.yaml")
    if image_match_path.exists():
        try:
            image_settings = ImageMatchingSettings.load_from_yaml(
                image_match_path
            )
            settings.image_matching = image_settings
        except ValidationError as e:
            logger.warning("画像マッチング設定の読み込みに失敗", exc_info=e)
            image_settings = settings.image_matching
    else:
        image_settings = settings.image_matching

    container.register(ImageMatchingSettings, instance=image_settings)

    # アダプタ登録
    container.register(VideoRecorder, OBSController)
    container.register(CaptureDevicePort, CaptureDeviceChecker)
    container.register(OBSControlPort, OBSController)
    container.register(VideoEditorPort, VideoEditor)
    container.register(UploadPort, YouTubeClient)
    container.register(PowerPort, SystemPower)
    if settings.game_mode == "salmon":
        container.register(AnalyzerPlugin, SalmonFrameAnalyzer)
    else:
        container.register(AnalyzerPlugin, BattleFrameAnalyzer)
    container.register(FrameAnalyzerPort, FrameAnalyzer)
    container.register(SpeechTranscriberPort, SpeechTranscriber)
    container.register(MetadataExtractorPort, MetadataExtractor)
    container.register(GroqClient, GroqClient)
    container.register(FFmpegProcessor, FFmpegProcessor)
    container.register(
        FileMetadataRepository,
        FileMetadataRepository,
        base_dir=Path("metadata"),
    )
    container.register(
        MetadataRepository,
        FileMetadataRepository,
        base_dir=Path("metadata"),
    )
    state_machine = StateMachine()
    container.register(StateMachine, instance=state_machine)

    # ユースケース登録
    container.register(RecordBattleUseCase, RecordBattleUseCase)
    container.register(PauseRecordingUseCase, PauseRecordingUseCase)
    container.register(ResumeRecordingUseCase, ResumeRecordingUseCase)
    container.register(StopRecordingUseCase, StopRecordingUseCase)
    container.register(ProcessPostGameUseCase, ProcessPostGameUseCase)
    container.register(UploadVideoUseCase, UploadVideoUseCase)
    container.register(ShutdownPCUseCase, ShutdownPCUseCase)
    container.register(
        InitializeEnvironmentUseCase, InitializeEnvironmentUseCase
    )
    container.register(CheckInitializationUseCase, CheckInitializationUseCase)
    container.register(DaemonUseCase, DaemonUseCase)

    return container
