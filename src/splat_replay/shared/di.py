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
    FFmpegProcessor,
    FileVideoAssetRepository,
    OBSController,
    SystemPower,
    FrameAnalyzer,
    YouTubeClient
)
from splat_replay.infrastructure.analyzers.plugin import AnalyzerPlugin
from splat_replay.infrastructure.analyzers.splatoon_battle_analyzer import (
    BattleFrameAnalyzer,
)
from splat_replay.infrastructure.analyzers.splatoon_salmon_analyzer import (
    SalmonFrameAnalyzer,
)
from splat_replay.domain.services.state_machine import StateMachine
from splat_replay.domain.services.editor import VideoEditor
from splat_replay.domain.services.uploader import YouTubeUploader
from splat_replay.infrastructure.audio.speech_transcriber import SpeechTranscriber
from splat_replay.application.interfaces import (
    VideoRecorder,
    VideoEditorPort,
    UploadPort,
    PowerPort,
    FrameAnalyzerPort,
    SpeechTranscriberPort,
    OBSControlPort,
    VideoAssetRepository,
)
from splat_replay.shared.config import (
    AppSettings,
    CaptureDeviceSettings,
    OBSSettings,
    RecordSettings,
    SpeechTranscriberSettings,
    VideoStorageSettings,
    VideoEditSettings,
    YouTubeSettings,
    PCSettings,
    ImageMatchingSettings,
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
    container.register(CaptureDeviceSettings, instance=settings.capture_device)
    container.register(OBSSettings, instance=settings.obs)
    container.register(RecordSettings, instance=settings.record)
    container.register(
        SpeechTranscriberSettings, instance=settings.speech_transcriber
    )
    container.register(VideoStorageSettings, instance=settings.storage)
    container.register(VideoEditSettings, instance=settings.video_edit)
    container.register(YouTubeSettings, instance=settings.youtube)
    container.register(PCSettings, instance=settings.pc)

    image_match_path = Path("config/image_matching.yaml")
    if not image_match_path.exists():
        raise FileNotFoundError(
            f"画像マッチング設定ファイルが見つかりません: {image_match_path}"
        )
    image_settings = ImageMatchingSettings.load_from_yaml(image_match_path)

    container.register(ImageMatchingSettings, instance=image_settings)

    # アダプタ登録
    container.register(VideoRecorder, OBSController)
    container.register(OBSControlPort, OBSController)
    container.register(VideoEditorPort, VideoEditor)
    container.register(UploadPort, YouTubeUploader)
    container.register(YouTubeClient, YouTubeClient)
    container.register(PowerPort, SystemPower)
    container.register(BattleFrameAnalyzer, BattleFrameAnalyzer)
    container.register(SalmonFrameAnalyzer, SalmonFrameAnalyzer)
    container.register(AnalyzerPlugin, BattleFrameAnalyzer)
    container.register(AnalyzerPlugin, SalmonFrameAnalyzer)
    container.register(FrameAnalyzerPort, FrameAnalyzer)
    container.register(SpeechTranscriberPort, SpeechTranscriber)
    container.register(FFmpegProcessor, FFmpegProcessor)
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
