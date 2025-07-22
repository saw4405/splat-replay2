from pathlib import Path
import tomllib

from pydantic import BaseModel

from splat_replay.shared.config.capture_device import CaptureDeviceSettings
from splat_replay.shared.config.obs import OBSSettings
from splat_replay.shared.config.record import RecordSettings
from splat_replay.shared.config.speech_transcriber import SpeechTranscriberSettings
from splat_replay.shared.config.video_storage import VideoStorageSettings
from splat_replay.shared.config.video_edit import VideoEditSettings
from splat_replay.shared.config.upload import UploadSettings
from splat_replay.shared.config.pc import PCSettings


class AppSettings(BaseModel):
    """アプリケーション全体の設定。"""
    capture_device: CaptureDeviceSettings = CaptureDeviceSettings()
    obs: OBSSettings = OBSSettings()
    record: RecordSettings = RecordSettings()
    speech_transcriber: SpeechTranscriberSettings = SpeechTranscriberSettings()
    storage: VideoStorageSettings = VideoStorageSettings()
    video_edit: VideoEditSettings = VideoEditSettings()
    upload: UploadSettings = UploadSettings()
    pc: PCSettings = PCSettings()

    class Config:
        pass

    @classmethod
    def load_from_toml(cls, path: Path) -> "AppSettings":
        """TOML ファイルから設定を読み込む。"""
        with path.open("rb") as f:
            raw = tomllib.load(f)
        section_classes = {
            "capture_device": CaptureDeviceSettings,
            "obs": OBSSettings,
            "record": RecordSettings,
            "speech_transcriber": SpeechTranscriberSettings,
            "storage": VideoStorageSettings,
            "video_edit": VideoEditSettings,
            "upload": UploadSettings,
            "pc": PCSettings,
        }
        kwargs = {}
        for section, cls_ in section_classes.items():
            if section in raw:
                kwargs[section] = cls_(**raw[section])
        return cls(**kwargs)
