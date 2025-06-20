"""DI コンテナ設定モジュール。"""

from __future__ import annotations

from pathlib import Path

import punq

from splat_replay.application import (
    ProcessPostGameUseCase,
    RecordBattleUseCase,
    PauseRecordingUseCase,
    ResumeRecordingUseCase,
    StopRecordingUseCase,
    ShutdownPCUseCase,
    UploadVideoUseCase,
    DaemonUseCase,
)
from splat_replay.infrastructure import (
    FFmpegProcessor,
    FileMetadataRepository,
    GroqClient,
    OBSController,
    SystemPower,
    YouTubeClient,
)
from splat_replay.domain.services import (
    VideoEditor,
    ScreenAnalyzer,
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
    ScreenAnalyzerPort,
    SpeechTranscriberPort,
    MetadataExtractorPort,
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

    container = punq.Container()

    settings = AppSettings()
    # 設定オブジェクトを登録
    container.register(AppSettings, instance=settings)
    container.register(YouTubeSettings, instance=settings.youtube)
    container.register(VideoEditSettings, instance=settings.video_edit)
    container.register(OBSSettings, instance=settings.obs)
    container.register(ImageMatchingSettings, instance=settings.image_matching)

    # アダプタ登録
    container.register(VideoRecorder, OBSController)
    container.register(VideoEditorPort, VideoEditor)
    container.register(UploadPort, YouTubeClient)
    container.register(PowerPort, SystemPower)
    container.register(ScreenAnalyzerPort, ScreenAnalyzer)
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
    container.register(DaemonUseCase, DaemonUseCase)

    return container
