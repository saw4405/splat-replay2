"""DI Container: Configuration registration.

Phase 3 リファクタリング - 設定値の登録を分離。
"""

from __future__ import annotations

from pathlib import Path

import punq

from splat_replay.application.interfaces import (
    BehaviorSettingsView,
    CaptureDeviceSettingsView,
    OBSSettingsView,
    SpeechSettingsView,
    UploadSettingsView,
    VideoEditSettingsView,
)
from splat_replay.domain.config import (
    AppSettings,
    BehaviorSettings,
    CaptureDeviceSettings,
    ImageMatchingSettings,
    OBSSettings,
    RecordSettings,
    SpeechTranscriberSettings,
    UploadSettings,
    VideoEditSettings,
    VideoStorageSettings,
)
from splat_replay.infrastructure.config import load_settings_from_toml
from splat_replay.infrastructure.filesystem import paths


def register_config(container: punq.Container) -> AppSettings:
    """設定を DI コンテナに登録する。"""
    settings = load_settings_from_toml()
    container.register(BehaviorSettings, instance=settings.behavior)
    container.register(BehaviorSettingsView, instance=settings.behavior)
    container.register(CaptureDeviceSettings, instance=settings.capture_device)
    container.register(
        CaptureDeviceSettingsView, instance=settings.capture_device
    )
    container.register(OBSSettings, instance=settings.obs)
    container.register(OBSSettingsView, instance=settings.obs)
    container.register(RecordSettings, instance=settings.record)
    container.register(
        SpeechTranscriberSettings, instance=settings.speech_transcriber
    )
    container.register(
        SpeechSettingsView, instance=settings.speech_transcriber
    )
    container.register(VideoStorageSettings, instance=settings.storage)
    container.register(VideoEditSettings, instance=settings.video_edit)
    container.register(VideoEditSettingsView, instance=settings.video_edit)
    container.register(UploadSettings, instance=settings.upload)
    container.register(UploadSettingsView, instance=settings.upload)
    return settings


def register_image_matching_settings(
    container: punq.Container, path: Path | None = None
) -> ImageMatchingSettings:
    """画像マッチング設定を DI コンテナに登録する。"""
    if path is None:
        path = paths.IMAGE_MATCHING_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"画像マッチング設定ファイルが見つかりません: {path}"
        )
    image_settings = ImageMatchingSettings.load_from_yaml(path)
    container.register(ImageMatchingSettings, instance=image_settings)
    return image_settings
