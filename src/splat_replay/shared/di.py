"""DI コンテナ設定モジュール。"""

from __future__ import annotations

from pathlib import Path

import punq

from splat_replay.application import AutoUseCase, UploadUseCase
from splat_replay.application.services import (
    EnvironmentInitializer,
    AutoRecorder,
    AutoEditor,
    AutoUploader,
    PowerManager,
)
from splat_replay.infrastructure import (
    CaptureDeviceChecker,
    FFmpegProcessor,
    FileMetadataRepository,
    FileVideoAssetRepository,
    OBSController,
    SystemPower,
    YouTubeClient,
    FrameAnalyzer,
)
from splat_replay.infrastructure.analyzers.plugin import AnalyzerPlugin
from splat_replay.infrastructure.analyzers.splatoon_battle_analyzer import (
    BattleFrameAnalyzer,
)
from splat_replay.infrastructure.analyzers.splatoon_salmon_analyzer import (
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
    VideoAssetRepository,
)
from splat_replay.shared.config import (
    AppSettings,
    YouTubeSettings,
    VideoEditSettings,
    OBSSettings,
    ImageMatchingSettings,
    SpeechTranscriberSettings,
    VideoStorageSettings,
)


def configure_container() -> punq.Container:
    """アプリで利用する依存関係を登録する。"""

    container = punq.Container()

    settings_path = Path("config/settings.toml")
    # settings.toml が存在する場合はそこから設定を読み込む
    if not settings_path.exists():
        raise FileNotFoundError(
            f"設定ファイルが見つかりません: {settings_path}"
        )
    settings = AppSettings.load_from_toml(settings_path)
    # 設定オブジェクトを登録
    container.register(AppSettings, instance=settings)
    container.register(YouTubeSettings, instance=settings.youtube)
    container.register(VideoEditSettings, instance=settings.video_edit)
    container.register(OBSSettings, instance=settings.obs)
    container.register(
        SpeechTranscriberSettings, instance=settings.speech_transcriber
    )
    container.register(VideoStorageSettings, instance=settings.storage)

    image_match_path = Path("config/image_matching.yaml")
    if not image_match_path.exists():
        raise FileNotFoundError(
            f"画像マッチング設定ファイルが見つかりません: {image_match_path}"
        )
    image_settings = ImageMatchingSettings.load_from_yaml(image_match_path)

    container.register(ImageMatchingSettings, instance=image_settings)

    # アダプタ登録
    container.register(VideoRecorder, OBSController)
    container.register(CaptureDevicePort, CaptureDeviceChecker)
    container.register(OBSControlPort, OBSController)
    container.register(VideoEditorPort, VideoEditor)
    container.register(UploadPort, YouTubeClient)
    container.register(PowerPort, SystemPower)
    container.register(BattleFrameAnalyzer, BattleFrameAnalyzer)
    container.register(SalmonFrameAnalyzer, SalmonFrameAnalyzer)
    container.register(AnalyzerPlugin, BattleFrameAnalyzer)
    container.register(AnalyzerPlugin, SalmonFrameAnalyzer)
    container.register(FrameAnalyzerPort, FrameAnalyzer)
    container.register(SpeechTranscriberPort, SpeechTranscriber)
    container.register(MetadataExtractorPort, MetadataExtractor)
    container.register(FFmpegProcessor, FFmpegProcessor)
    container.register(
        FileMetadataRepository,
        FileMetadataRepository,
        base_dir=Path("metadata"),
    )
    container.register(
        FileVideoAssetRepository,
        FileVideoAssetRepository,
        settings=settings.storage,
    )
    container.register(
        MetadataRepository,
        FileMetadataRepository,
        base_dir=Path("metadata"),
    )
    container.register(
        VideoAssetRepository,
        FileVideoAssetRepository,
        settings=settings.storage,
    )
    state_machine = StateMachine()
    container.register(StateMachine, instance=state_machine)

    # サービス登録
    container.register(EnvironmentInitializer, EnvironmentInitializer)
    container.register(AutoRecorder, AutoRecorder)
    container.register(AutoEditor, AutoEditor)
    container.register(AutoUploader, AutoUploader)
    container.register(PowerManager, PowerManager)

    # ユースケース登録
    container.register(AutoUseCase, AutoUseCase)
    container.register(UploadUseCase, UploadUseCase)
    return container
