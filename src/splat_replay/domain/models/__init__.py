"""ドメインモデル公開API。"""

__all__ = [
    "Frame",
    "as_frame",
    "Rule",
    "Stage",
    "GameMode",
    "Match",
    "RateBase",
    "XP",
    "Udemae",
    "Result",
    "BattleResult",
    "SalmonResult",
    "RecordingMetadata",
    "VideoAsset",
    "TIME_RANGES",
]

from .aliases import Frame, as_frame
from .rule import Rule
from .stage import Stage
from .game_mode import GameMode
from .match import Match
from .rate import RateBase, XP, Udemae
from .result import Result, BattleResult, SalmonResult
from .recording_metadata import RecordingMetadata
from .video_asset import VideoAsset
from .time_schedule import TIME_RANGES
