from __future__ import annotations

from pydantic import BaseModel

from splat_replay.domain.config.behavior import BehaviorSettings
from splat_replay.domain.config.capture_device import CaptureDeviceSettings
from splat_replay.domain.config.obs import OBSSettings
from splat_replay.domain.config.record import RecordSettings
from splat_replay.domain.config.speech_transcriber import (
    SpeechTranscriberSettings,
)
from splat_replay.domain.config.upload import UploadSettings
from splat_replay.domain.config.video_edit import VideoEditSettings
from splat_replay.domain.config.video_storage import VideoStorageSettings

SECTION_CLASSES = {
    "behavior": BehaviorSettings,
    "capture_device": CaptureDeviceSettings,
    "obs": OBSSettings,
    "record": RecordSettings,
    "speech_transcriber": SpeechTranscriberSettings,
    "storage": VideoStorageSettings,
    "video_edit": VideoEditSettings,
    "upload": UploadSettings,
}


class AppSettings(BaseModel):
    """アプリケーション全体の設定。"""

    behavior: BehaviorSettings = BehaviorSettings()
    capture_device: CaptureDeviceSettings = CaptureDeviceSettings()
    obs: OBSSettings = OBSSettings()
    record: RecordSettings = RecordSettings()
    speech_transcriber: SpeechTranscriberSettings = SpeechTranscriberSettings()
    storage: VideoStorageSettings = VideoStorageSettings()
    video_edit: VideoEditSettings = VideoEditSettings()
    upload: UploadSettings = UploadSettings()
