"""インフラ層公開API。"""

__all__ = [
    "OBSController",
    "FFmpegProcessor",
    "GroqClient",
    "YouTubeClient",
    "SystemPower",
    "CaptureDeviceChecker",
    "FrameAnalyzer",
    "BattleFrameAnalyzer",
    "SalmonFrameAnalyzer",
    "SplatoonSalmonAnalyzer",
    "FileMetadataRepository",
    "FileVideoAssetRepository",
]

from .adapters.obs_controller import OBSController
from .adapters.ffmpeg_processor import FFmpegProcessor
from .adapters.groq_client import GroqClient
from .adapters.youtube_client import YouTubeClient
from .adapters.system_power import SystemPower
from .adapters.capture_device_checker import CaptureDeviceChecker
from .analyzers.frame_analyzer import FrameAnalyzer
from .analyzers.splatoon_battle_analyzer import BattleFrameAnalyzer
from .analyzers.splatoon_salmon_analyzer import SalmonFrameAnalyzer
from .repositories.file_metadata_repo import FileMetadataRepository
from .repositories.video_asset_repo import FileVideoAssetRepository

SplatoonSalmonAnalyzer = SalmonFrameAnalyzer
