"""各種アダプタ実装を公開するモジュール。"""

__all__ = [
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
]

from .audio import (
    GoogleTextToSpeech,
    IntegratedSpeechRecognizer,
    MicrophoneEnumerator,
    SpeechTranscriber,
)
from .capture.capture import Capture
from .capture.capture_device_checker import (
    CaptureDeviceChecker,
    CaptureDeviceEnumerator,
)
from .capture.ndi_capture import NDICapture
from .image.image_drawer import ImageDrawer
from .image.image_editor import ImageEditor
from .messaging.event_bus_adapter import EventBusPortAdapter
from .messaging.event_publisher_adapter import EventPublisherAdapter
from .messaging.frame_publisher_adapter import FramePublisherAdapter
from .obs.recorder_controller import OBSRecorderController
from .storage.settings_repository import TomlSettingsRepository
from .storage.setup_state_file_adapter import SetupStateFileAdapter
from .system.cross_cutting import (
    FileSystemPathsAdapter,
    LocalFileSystemAdapter,
    ProcessEnvironmentAdapter,
    StructlogLoggerAdapter,
    TomlConfigAdapter,
)
from .system.gui_runtime_port_adapter import GuiRuntimePortAdapter
from .system.system_command_adapter import SystemCommandAdapter
from .system.system_power import SystemPower
from .text.subtitle_editor import SubtitleEditor
from .text.tesseract_ocr import TesseractOCR
from .upload.youtube_client import YouTubeClient
from .video.ffmpeg_processor import FFmpegProcessor
from .video.recorder_with_transcription import RecorderWithTranscription
from .weapon_detection import WeaponRecognitionAdapter
