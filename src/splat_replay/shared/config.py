"""アプリ全体の設定管理モジュール。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Literal

from pydantic import BaseModel, BaseSettings


class YouTubeSettings(BaseSettings):
    """YouTube アップロード関連の設定。"""

    visibility: Literal["public", "unlisted", "private"] = "private"
    title_template: str = (
        "{MATCH}({RATE}) {RULE} {WIN}勝{LOSE}敗 {DAY} {SCHEDULE}時～"
    )
    description_template: str = "{CHAPTERS}"
    chapter_template: str = "{RESULT} {KILL}k {DEATH}d {SPECIAL}s  {STAGE}"
    tags: List[str] = ["スプラトゥーン3"]
    playlist_id: Optional[str] = None

    class Config(BaseSettings.Config):
        env_prefix = "YOUTUBE_"
        env_file = ".env"


class VideoEditSettings(BaseSettings):
    """動画編集処理の設定。"""

    volume_multiplier: float = 1.0

    class Config(BaseSettings.Config):
        env_prefix = "VIDEO_EDIT_"
        env_file = ".env"


class OBSSettings(BaseSettings):
    """OBS 接続設定。"""

    websocket_host: str = "localhost"
    websocket_port: int = 4455
    websocket_password: str = ""
    executable_path: Path = Path("obs")
    capture_device_name: str = "USB Video"

    class Config(BaseSettings.Config):
        env_prefix = "OBS_"
        env_file = ".env"


class MatcherConfig(BaseModel):
    """画像マッチング1件分の設定。"""

    type: Literal["template", "hsv", "rgb", "hash", "uniform"]
    threshold: float = 0.8
    template_path: Optional[str] = None
    lower_bound: Optional[List[int]] = None
    upper_bound: Optional[List[int]] = None
    rgb: Optional[List[int]] = None
    hue_threshold: Optional[float] = None


class ImageMatchingSettings(BaseSettings):
    """画像解析用のマッチャー設定。"""

    matchers: Dict[str, MatcherConfig] = {}

    class Config(BaseSettings.Config):
        env_prefix = "MATCHING_"
        env_file = ".env"


class AppSettings(BaseSettings):
    """アプリケーション全体の設定。"""

    youtube: YouTubeSettings = YouTubeSettings()
    video_edit: VideoEditSettings = VideoEditSettings()
    obs: OBSSettings = OBSSettings()
    image_matching: ImageMatchingSettings = ImageMatchingSettings()

    class Config(BaseSettings.Config):
        env_file = ".env"

    @classmethod
    def load_from_toml(cls, path: Path) -> "AppSettings":
        """TOML ファイルから設定を読み込む (簡易実装)。"""
        _ = path  # 実装は後で追加
        return cls()
