"""Domain layer: Configuration models (business rules)."""

from splat_replay.domain.config.app import SECTION_CLASSES, AppSettings
from splat_replay.domain.config.behavior import BehaviorSettings
from splat_replay.domain.config.capture_device import CaptureDeviceSettings
from splat_replay.domain.config.image_matching import (
    CompositeMatcherConfig,
    ImageMatchingSettings,
    MatcherConfig,
    MatchExpression,
)
from splat_replay.domain.config.obs import OBSSettings
from splat_replay.domain.config.record import RecordSettings
from splat_replay.domain.config.speech_transcriber import (
    SpeechTranscriberSettings,
)
from splat_replay.domain.config.upload import UploadSettings
from splat_replay.domain.config.video_edit import VideoEditSettings
from splat_replay.domain.config.video_storage import VideoStorageSettings

__all__ = [
    "SECTION_CLASSES",
    "AppSettings",
    "BehaviorSettings",
    "CaptureDeviceSettings",
    "CompositeMatcherConfig",
    "ImageMatchingSettings",
    "MatchExpression",
    "MatcherConfig",
    "OBSSettings",
    "RecordSettings",
    "SpeechTranscriberSettings",
    "UploadSettings",
    "VideoEditSettings",
    "VideoStorageSettings",
]
