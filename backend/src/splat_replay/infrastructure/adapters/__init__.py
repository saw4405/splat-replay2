"""インフラ adapter 群の公開 API。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AdaptiveCapture",
    "AdaptiveCaptureDeviceChecker",
    "AdaptiveVideoRecorder",
    "CaptureDeviceChecker",
    "CaptureDeviceEnumerator",
    "NDICapture",
    "Capture",
    "OBSRecorderController",
    "RecorderWithTranscription",
    "FFmpegProcessor",
    "YouTubeClient",
    "SystemPower",
    "TesseractOCR",
    "ImageEditor",
    "SubtitleEditor",
    "ImageDrawer",
    "IntegratedSpeechRecognizer",
    "MicrophoneEnumerator",
    "SpeechTranscriber",
    "GoogleTextToSpeech",
    "BattleMedalRecognizerAdapter",
    "EventPublisherAdapter",
    "EventBusPortAdapter",
    "FramePublisherAdapter",
    "GuiRuntimePortAdapter",
    "SetupStateFileAdapter",
    "SystemCommandAdapter",
    "StructlogLoggerAdapter",
    "TomlConfigAdapter",
    "FileSystemPathsAdapter",
    "LocalFileSystemAdapter",
    "ProcessEnvironmentAdapter",
    "TomlSettingsRepository",
    "WeaponRecognitionAdapter",
    "VideoFileCapture",
    "ReplayRecorderController",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AdaptiveCapture": (".capture.adaptive_capture", "AdaptiveCapture"),
    "AdaptiveCaptureDeviceChecker": (
        ".capture.adaptive_capture_device_checker",
        "AdaptiveCaptureDeviceChecker",
    ),
    "AdaptiveVideoRecorder": (
        ".video.adaptive_video_recorder",
        "AdaptiveVideoRecorder",
    ),
    "BattleMedalRecognizerAdapter": (
        ".medal_detection",
        "BattleMedalRecognizerAdapter",
    ),
    "Capture": (".capture.capture", "Capture"),
    "CaptureDeviceChecker": (
        ".capture.capture_device_checker",
        "CaptureDeviceChecker",
    ),
    "CaptureDeviceEnumerator": (
        ".capture.capture_device_checker",
        "CaptureDeviceEnumerator",
    ),
    "EventBusPortAdapter": (
        ".messaging.event_bus_adapter",
        "EventBusPortAdapter",
    ),
    "EventPublisherAdapter": (
        ".messaging.event_publisher_adapter",
        "EventPublisherAdapter",
    ),
    "FFmpegProcessor": (".video.ffmpeg_processor", "FFmpegProcessor"),
    "FileSystemPathsAdapter": (
        ".system.cross_cutting",
        "FileSystemPathsAdapter",
    ),
    "FramePublisherAdapter": (
        ".messaging.frame_publisher_adapter",
        "FramePublisherAdapter",
    ),
    "GoogleTextToSpeech": (
        ".audio.google_text_to_speech",
        "GoogleTextToSpeech",
    ),
    "GuiRuntimePortAdapter": (
        ".system.gui_runtime_port_adapter",
        "GuiRuntimePortAdapter",
    ),
    "ImageDrawer": (".image.image_drawer", "ImageDrawer"),
    "ImageEditor": (".image.image_editor", "ImageEditor"),
    "IntegratedSpeechRecognizer": (
        ".audio.integrated_speech_recognition",
        "IntegratedSpeechRecognizer",
    ),
    "LocalFileSystemAdapter": (
        ".system.cross_cutting",
        "LocalFileSystemAdapter",
    ),
    "MicrophoneEnumerator": (
        ".audio.microphone_enumerator",
        "MicrophoneEnumerator",
    ),
    "NDICapture": (".capture.ndi_capture", "NDICapture"),
    "OBSRecorderController": (
        ".obs.recorder_controller",
        "OBSRecorderController",
    ),
    "ProcessEnvironmentAdapter": (
        ".system.cross_cutting",
        "ProcessEnvironmentAdapter",
    ),
    "RecorderWithTranscription": (
        ".video.recorder_with_transcription",
        "RecorderWithTranscription",
    ),
    "ReplayRecorderController": (
        ".video.replay_recorder_controller",
        "ReplayRecorderController",
    ),
    "SetupStateFileAdapter": (
        ".storage.setup_state_file_adapter",
        "SetupStateFileAdapter",
    ),
    "SpeechTranscriber": (".audio.speech_transcriber", "SpeechTranscriber"),
    "StructlogLoggerAdapter": (
        ".system.cross_cutting",
        "StructlogLoggerAdapter",
    ),
    "SubtitleEditor": (".text.subtitle_editor", "SubtitleEditor"),
    "SystemCommandAdapter": (
        ".system.system_command_adapter",
        "SystemCommandAdapter",
    ),
    "SystemPower": (".system.system_power", "SystemPower"),
    "TesseractOCR": (".text.tesseract_ocr", "TesseractOCR"),
    "TomlConfigAdapter": (".system.cross_cutting", "TomlConfigAdapter"),
    "TomlSettingsRepository": (
        ".storage.settings_repository",
        "TomlSettingsRepository",
    ),
    "VideoFileCapture": (".capture.video_file_capture", "VideoFileCapture"),
    "WeaponRecognitionAdapter": (
        ".weapon_detection",
        "WeaponRecognitionAdapter",
    ),
    "YouTubeClient": (".upload.youtube_client", "YouTubeClient"),
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
