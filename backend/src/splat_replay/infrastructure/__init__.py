"""インフラ層の公開 API。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from . import filesystem, logging

__all__ = [
    "filesystem",
    "logging",
    "MatcherRegistry",
    "AdaptiveCapture",
    "AdaptiveCaptureDeviceChecker",
    "AdaptiveVideoRecorder",
    "CaptureDeviceChecker",
    "CaptureDeviceEnumerator",
    "Capture",
    "NDICapture",
    "OBSRecorderController",
    "RecorderWithTranscription",
    "FFmpegProcessor",
    "YouTubeClient",
    "EventPublisherAdapter",
    "EventBusPortAdapter",
    "FramePublisherAdapter",
    "GuiRuntimePortAdapter",
    "SystemPower",
    "TesseractOCR",
    "SubtitleEditor",
    "ImageDrawer",
    "IntegratedSpeechRecognizer",
    "MicrophoneEnumerator",
    "SpeechTranscriber",
    "GoogleTextToSpeech",
    "BattleMedalRecognizerAdapter",
    "FileBattleHistoryRepository",
    "FileVideoAssetRepository",
    "SetupStateFileAdapter",
    "SystemCommandAdapter",
    "StructlogLoggerAdapter",
    "TomlConfigAdapter",
    "TomlSettingsRepository",
    "FileSystemPathsAdapter",
    "LocalFileSystemAdapter",
    "ProcessEnvironmentAdapter",
    "ReplayRecorderController",
    "VideoFileCapture",
    "WeaponRecognitionAdapter",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AdaptiveCapture": (
        ".adapters.capture.adaptive_capture",
        "AdaptiveCapture",
    ),
    "AdaptiveCaptureDeviceChecker": (
        ".adapters.capture.adaptive_capture_device_checker",
        "AdaptiveCaptureDeviceChecker",
    ),
    "AdaptiveVideoRecorder": (
        ".adapters.video.adaptive_video_recorder",
        "AdaptiveVideoRecorder",
    ),
    "BattleMedalRecognizerAdapter": (
        ".adapters.medal_detection",
        "BattleMedalRecognizerAdapter",
    ),
    "Capture": (".adapters.capture.capture", "Capture"),
    "CaptureDeviceChecker": (
        ".adapters.capture.capture_device_checker",
        "CaptureDeviceChecker",
    ),
    "CaptureDeviceEnumerator": (
        ".adapters.capture.capture_device_checker",
        "CaptureDeviceEnumerator",
    ),
    "EventBusPortAdapter": (
        ".adapters.messaging.event_bus_adapter",
        "EventBusPortAdapter",
    ),
    "EventPublisherAdapter": (
        ".adapters.messaging.event_publisher_adapter",
        "EventPublisherAdapter",
    ),
    "FFmpegProcessor": (
        ".adapters.video.ffmpeg_processor",
        "FFmpegProcessor",
    ),
    "FileBattleHistoryRepository": (
        ".repositories.battle_history_repo",
        "FileBattleHistoryRepository",
    ),
    "FileSystemPathsAdapter": (
        ".adapters.system.cross_cutting",
        "FileSystemPathsAdapter",
    ),
    "FileVideoAssetRepository": (
        ".repositories.video_asset_repo",
        "FileVideoAssetRepository",
    ),
    "FramePublisherAdapter": (
        ".adapters.messaging.frame_publisher_adapter",
        "FramePublisherAdapter",
    ),
    "GoogleTextToSpeech": (
        ".adapters.audio.google_text_to_speech",
        "GoogleTextToSpeech",
    ),
    "GuiRuntimePortAdapter": (
        ".adapters.system.gui_runtime_port_adapter",
        "GuiRuntimePortAdapter",
    ),
    "ImageDrawer": (".adapters.image.image_drawer", "ImageDrawer"),
    "IntegratedSpeechRecognizer": (
        ".adapters.audio.integrated_speech_recognition",
        "IntegratedSpeechRecognizer",
    ),
    "LocalFileSystemAdapter": (
        ".adapters.system.cross_cutting",
        "LocalFileSystemAdapter",
    ),
    "MatcherRegistry": (".matchers", "MatcherRegistry"),
    "MicrophoneEnumerator": (
        ".adapters.audio.microphone_enumerator",
        "MicrophoneEnumerator",
    ),
    "NDICapture": (".adapters.capture.ndi_capture", "NDICapture"),
    "OBSRecorderController": (
        ".adapters.obs.recorder_controller",
        "OBSRecorderController",
    ),
    "ProcessEnvironmentAdapter": (
        ".adapters.system.cross_cutting",
        "ProcessEnvironmentAdapter",
    ),
    "RecorderWithTranscription": (
        ".adapters.video.recorder_with_transcription",
        "RecorderWithTranscription",
    ),
    "ReplayRecorderController": (
        ".adapters.video.replay_recorder_controller",
        "ReplayRecorderController",
    ),
    "SetupStateFileAdapter": (
        ".adapters.storage.setup_state_file_adapter",
        "SetupStateFileAdapter",
    ),
    "SpeechTranscriber": (
        ".adapters.audio.speech_transcriber",
        "SpeechTranscriber",
    ),
    "StructlogLoggerAdapter": (
        ".adapters.system.cross_cutting",
        "StructlogLoggerAdapter",
    ),
    "SubtitleEditor": (
        ".adapters.text.subtitle_editor",
        "SubtitleEditor",
    ),
    "SystemCommandAdapter": (
        ".adapters.system.system_command_adapter",
        "SystemCommandAdapter",
    ),
    "SystemPower": (".adapters.system.system_power", "SystemPower"),
    "TesseractOCR": (".adapters.text.tesseract_ocr", "TesseractOCR"),
    "TomlConfigAdapter": (
        ".adapters.system.cross_cutting",
        "TomlConfigAdapter",
    ),
    "TomlSettingsRepository": (
        ".adapters.storage.settings_repository",
        "TomlSettingsRepository",
    ),
    "VideoFileCapture": (
        ".adapters.capture.video_file_capture",
        "VideoFileCapture",
    ),
    "WeaponRecognitionAdapter": (
        ".adapters.weapon_detection",
        "WeaponRecognitionAdapter",
    ),
    "YouTubeClient": (".adapters.upload.youtube_client", "YouTubeClient"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _LAZY_EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
