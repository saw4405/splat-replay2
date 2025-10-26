"""各種アダプタ実装を公開するモジュール。"""

__all__ = [
    "CaptureDeviceChecker",
    "NDICapture",
    "Capture",
    "OBSController",
    "RecorderWithTranscription",
    "FFmpegProcessor",
    "YouTubeClient",
    "SystemPower",
    "TesseractOCR",
    "ImageEditor",
    "SubtitleEditor",
    "ImageDrawer",
    "IntegratedSpeechRecognizer",
    "SpeechTranscriber",
    "GoogleTextToSpeech",
    "EventPublisherAdapter",
    "FramePublisherAdapter",
    "GuiRuntimePortAdapter",
]

from .audio import (
    GoogleTextToSpeech,
    IntegratedSpeechRecognizer,
    SpeechTranscriber,
)
from .capture import Capture
from .capture_device_checker import CaptureDeviceChecker
from .event_publisher_adapter import EventPublisherAdapter
from .ffmpeg_processor import FFmpegProcessor
from .frame_publisher_adapter import FramePublisherAdapter
from .gui_runtime_port_adapter import GuiRuntimePortAdapter
from .image_drawer import ImageDrawer
from .image_editor import ImageEditor
from .ndi_capture import NDICapture
from .obs_controller import OBSController
from .recorder_with_transcription import RecorderWithTranscription
from .subtitle_editor import SubtitleEditor
from .system_power import SystemPower
from .tesseract_ocr import TesseractOCR
from .youtube_client import YouTubeClient
