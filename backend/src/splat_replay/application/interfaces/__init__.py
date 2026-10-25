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
    ClockPort,
    ConfigPort,
    FileSystemPort,
    LoggerPort,
    PathsPort,
    RequiredSetupConfigPort,
)
from splat_replay.application.interfaces.history import (
    BattleHistoryEntry,
    BattleHistoryRepositoryPort,
)
from splat_replay.application.interfaces.data import (
    AudioInputHealthCheckResult,
    AudioInputHealthStatus,
    BehaviorSettingsView,
    Caption,
    CaptureDeviceSettingsView,
    FileStats,
    OBSSettingsView,
    PrivacyStatus,
    SectionUpdate,
    SettingDisplayLevel,
    SettingFieldData,
    SettingRequirement,
    SettingSectionData,
    SettingsRepositoryPort,
    SpeechAudioEncoding,
    SpeechSettingsView,
    SpeechTranscriberSettingsView,
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
from splat_replay.application.interfaces.notification import (
    DesktopNotificationPort,
)
from splat_replay.application.interfaces.required_setup import (
    RequiredSetupIssue,
    RequiredSetupIssueCachePort,
)
from splat_replay.application.interfaces.recording import (
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CapturePort,
    ReplayBootstrapResolverPort,
    RecorderStatus,
    RecorderWithTranscriptionPort,
    VideoRecorderPort,
)
from splat_replay.application.interfaces.system import (
    CommandExecutionError,
    CommandResult,
    EnvironmentPort,
    PowerPort,
    SoftwareInstallAttempt,
    SoftwareInstallerPort,
    SystemCommandPort,
)
from splat_replay.application.interfaces.upload import (
    AuthenticatedClientPort,
    UploadPort,
)
from splat_replay.application.interfaces.thumbnail_rule_image import (
    ThumbnailRuleImageResolverPort,
)
from splat_replay.application.interfaces.video import (
    FramePreviewPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
    VideoPreviewError,
    VideoPreviewPort,
    VideoPreviewUnavailableError,
)
from splat_replay.application.interfaces.weapon_detection import (
    WeaponCandidateScore,
    WeaponDisplayDetectionResult,
    WeaponRecognitionPort,
    WeaponRecognitionResult,
    WeaponSlotResult,
)
from splat_replay.application.interfaces.xp_detection_diagnostics import (
    XPDetectionDiagnosticsPort,
    XPDetectionDiagnosticsRecord,
)
from splat_replay.application.interfaces.system import (
    OBSMainOutputCheckResult,
    OBSConfigurationCheckerPort,
    OBSMainOutputStatus,
    OBSWebSocketCheckResult,
    OBSWebSocketStatus,
)

# Domain Service用ポートはDomain層からインポート（ポート配置ルールに準拠）
from splat_replay.domain.ports import ImageMatcherPort, OCRPort

__all__ = [
    # Common
    "BattleHistoryEntry",
    "BattleHistoryRepositoryPort",
    "ClockPort",
    "ConfigPort",
    "FileSystemPort",
    "LoggerPort",
    "PathsPort",
    "RequiredSetupConfigPort",
    "ThumbnailRuleImageResolverPort",
    # Data
    "AudioInputHealthCheckResult",
    "AudioInputHealthStatus",
    "BehaviorSettingsView",
    "Caption",
    "CaptureDeviceSettingsView",
    "FileStats",
    "OBSSettingsView",
    "OBSMainOutputCheckResult",
    "OBSConfigurationCheckerPort",
    "OBSMainOutputStatus",
    "OBSWebSocketCheckResult",
    "OBSWebSocketStatus",
    "PrivacyStatus",
    "SectionUpdate",
    "SettingDisplayLevel",
    "SettingFieldData",
    "SettingRequirement",
    "SettingSectionData",
    "SettingsRepositoryPort",
    "SpeechAudioEncoding",
    "SpeechSettingsView",
    "SpeechTranscriberSettingsView",
    "SpeechSynthesisRequest",
    "SpeechSynthesisResult",
    "UploadSettingsView",
    "VideoEditSettingsView",
    # Recording
    "CaptureDeviceEnumeratorPort",
    "CaptureDevicePort",
    "CapturePort",
    "ReplayBootstrapResolverPort",
    "RequiredSetupIssue",
    "RequiredSetupIssueCachePort",
    "RecorderStatus",
    "RecorderWithTranscriptionPort",
    "VideoRecorderPort",
    # Audio
    "MicrophoneEnumeratorPort",
    "SpeechTranscriberPort",
    "TextToSpeechPort",
    # Video
    "FramePreviewPort",
    "VideoAssetRepositoryPort",
    "VideoEditorPort",
    "VideoPreviewError",
    "VideoPreviewPort",
    "VideoPreviewUnavailableError",
    "WeaponCandidateScore",
    "WeaponDisplayDetectionResult",
    "WeaponRecognitionPort",
    "WeaponRecognitionResult",
    "WeaponSlotResult",
    "XPDetectionDiagnosticsPort",
    "XPDetectionDiagnosticsRecord",
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
    "PowerPort",
    "SoftwareInstallAttempt",
    "SoftwareInstallerPort",
    "SystemCommandPort",
    "DesktopNotificationPort",
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
