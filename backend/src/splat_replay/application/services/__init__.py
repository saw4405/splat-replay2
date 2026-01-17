"""アプリケーションサービス群。

Phase 9 リファクタリング:
- VideoGroupingService: VideoAsset のグループ化（AutoEditor から分離）
- TitleDescriptionGenerator: タイトル・説明生成（AutoEditor から分離）
- ThumbnailGenerator: サムネイル生成（AutoEditor から分離）
- SubtitleProcessor: 字幕処理・音声読み上げ（AutoEditor から分離）
"""

__all__ = [
    "DeviceChecker",
    "AutoRecorder",
    "AutoEditor",
    "AutoUploader",
    "PowerManager",
    "ProgressReporter",
    "ProgressEventStore",
    "SettingsService",
    "ProgressEvent",
    "RecordingPreparationService",
    "SystemCheckService",
    "SoftwareCheckResult",
    "SystemSetupService",
    "SetupService",
    "ErrorHandler",
    "ErrorResponse",
    "SetupError",
    "SystemCheckError",
    "SetupStateError",
    "FileOperationError",
    "NetworkError",
    "UserCancelledError",
    # Phase 9: 新しいサービス
    "VideoGroupingService",
    "TitleDescriptionGenerator",
    "ThumbnailGenerator",
    "SubtitleProcessor",
]

from .editing import (
    AutoEditor,
    SubtitleProcessor,
    ThumbnailGenerator,
    TitleDescriptionGenerator,
    VideoGroupingService,
)
from .errors import ErrorHandler, ErrorResponse
from .recording import AutoRecorder, RecordingPreparationService
from .setup import (
    SetupService,
    SoftwareCheckResult,
    SystemCheckService,
    SystemSetupService,
)
from .setup.setup_errors import (
    FileOperationError,
    NetworkError,
    SetupError,
    SetupStateError,
    SystemCheckError,
    UserCancelledError,
)
from .system import DeviceChecker, PowerManager
from .upload import AutoUploader
from .common import (
    ProgressEvent,
    ProgressEventStore,
    ProgressReporter,
    SettingsService,
)
