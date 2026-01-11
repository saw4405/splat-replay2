"""Application interfaces package - Domain-specific port definitions.

このパッケージは、610行の interfaces.py を責務別に分割したものです。
アプリケーション層の公開インターフェースとして __init__.py から再エクスポートします。

モジュール構成:
- common.py: 横断的関心事（Logger, Config, Paths）
- data.py: データ型・設定ビュー・TypedDict
- recording.py: 録画関連ポート
- video.py: 動画処理ポート
- audio.py: 音声処理ポート
- image.py: 画像処理ポート
- upload.py: アップロードポート
- system.py: システム制御ポート
- messaging.py: イベント・コマンドポート
"""

# Re-export all interfaces as public API
from splat_replay.application.interfaces.audio import (
    MicrophoneEnumeratorPort,
    SpeechTranscriberPort,
    TextToSpeechPort,
)
from splat_replay.application.interfaces.common import (
    ConfigPort,
    FileSystemPort,
    LoggerPort,
    PathsPort,
)
from splat_replay.application.interfaces.data import (
    BehaviorSettingsView,
    Caption,
    CaptureDeviceSettingsView,
    FileStats,
    OBSSettingsView,
    PrivacyStatus,
    SecretString,
    SectionUpdate,
    SettingFieldData,
    SettingSectionData,
    SettingsRepositoryPort,
    SpeechAudioEncoding,
    SpeechSettingsView,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    UploadSettingsView,
    VideoEditSettingsView,
)
from splat_replay.application.interfaces.image import (
    Color,
    ImageDrawerPort,
    ImageEditorPort,
    ImageSelector,
    SubtitleEditorPort,
)
from splat_replay.application.interfaces.messaging import (
    CommandDispatcher,
    DomainEventPublisher,
    EventBusPort,
    EventPublisher,
    EventSubscriber,
    EventSubscription,
    FramePublisher,
    FrameSource,
)
from splat_replay.application.interfaces.recording import (
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CapturePort,
    RecorderStatus,
    RecorderWithTranscriptionPort,
    VideoRecorderPort,
)
from splat_replay.application.interfaces.system import (
    CommandExecutionError,
    CommandResult,
    EnvironmentPort,
    InstallationStatePort,
    PowerPort,
    SystemCommandPort,
)
from splat_replay.application.interfaces.upload import (
    AuthenticatedClientPort,
    UploadPort,
)
from splat_replay.application.interfaces.video import (
    VideoAssetRepositoryPort,
    VideoEditorPort,
)

# Domain Service用ポートはDomain層からインポート（ポート配置ルールに準拠）
from splat_replay.domain.ports import ImageMatcherPort, OCRPort

__all__ = [
    # Common
    "ConfigPort",
    "FileSystemPort",
    "LoggerPort",
    "PathsPort",
    # Data
    "BehaviorSettingsView",
    "Caption",
    "CaptureDeviceSettingsView",
    "FileStats",
    "OBSSettingsView",
    "PrivacyStatus",
    "SecretString",
    "SectionUpdate",
    "SettingFieldData",
    "SettingSectionData",
    "SettingsRepositoryPort",
    "SpeechAudioEncoding",
    "SpeechSettingsView",
    "SpeechSynthesisRequest",
    "SpeechSynthesisResult",
    "UploadSettingsView",
    "VideoEditSettingsView",
    # Recording
    "CaptureDeviceEnumeratorPort",
    "CaptureDevicePort",
    "CapturePort",
    "RecorderStatus",
    "RecorderWithTranscriptionPort",
    "VideoRecorderPort",
    # Audio
    "MicrophoneEnumeratorPort",
    "SpeechTranscriberPort",
    "TextToSpeechPort",
    # Video
    "VideoAssetRepositoryPort",
    "VideoEditorPort",
    # Image
    "Color",
    "ImageDrawerPort",
    "ImageEditorPort",
    "ImageMatcherPort",
    "ImageSelector",
    "OCRPort",
    "SubtitleEditorPort",
    # Upload
    "AuthenticatedClientPort",
    "UploadPort",
    # System
    "CommandExecutionError",
    "CommandResult",
    "EnvironmentPort",
    "InstallationStatePort",
    "PowerPort",
    "SystemCommandPort",
    # Messaging
    "CommandDispatcher",
    "DomainEventPublisher",
    "EventBusPort",
    "EventMessage",
    "EventPublisher",
    "EventSubscriber",
    "EventSubscription",
    "FramePublisher",
    "FrameSource",
]
