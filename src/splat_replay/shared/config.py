"""アプリ全体の設定管理モジュール。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Literal
import tomllib

from pydantic import BaseModel


class YouTubeSettings(BaseModel):
    """YouTube アップロード関連の設定。"""

    enabled: bool = False
    client_secrets_file: str = "config/youtube_client_secrets.json"
    upload_privacy: Literal["public", "unlisted", "private"] = "private"
    title_template: Optional[str] = None
    description_template: Optional[str] = None
    chapter_template: Optional[str] = None
    tags: Optional[List[str]] = None
    playlist_id: Optional[str] = None

    class Config:
        pass


class VideoEditSettings(BaseModel):
    """動画編集処理の設定。"""

    volume_multiplier: float = 1.0

    class Config:
        pass


class OBSSettings(BaseModel):
    """OBS 接続設定。"""

    websocket_host: str = "localhost"
    websocket_port: int = 4455
    websocket_password: str = ""
    executable_path: Path = Path("obs")
    capture_device_name: Optional[str] = None
    capture_device_index: int = 0

    class Config:
        pass


class MatcherConfig(BaseModel):
    """画像マッチング1件分の設定。"""

    type: Literal["template", "hsv", "rgb", "hash", "uniform"]
    threshold: float = 0.8
    template_path: Optional[str] = None
    lower_bound: Optional[List[int]] = None
    upper_bound: Optional[List[int]] = None
    rgb: Optional[List[int]] = None
    hue_threshold: Optional[float] = None


class ImageMatchingSettings(BaseModel):
    """画像解析用のマッチャー設定。"""

    matchers: Dict[str, MatcherConfig] = {}

    class Config:
        pass


class AppSettings(BaseModel):
    """アプリケーション全体の設定。"""

    youtube: YouTubeSettings = YouTubeSettings()
    video_edit: VideoEditSettings = VideoEditSettings()
    obs: OBSSettings = OBSSettings()
    image_matching: ImageMatchingSettings = ImageMatchingSettings()

    class Config:
        pass

    @classmethod
    def load_from_toml(cls, path: Path) -> "AppSettings":
        """TOML ファイルから設定を読み込む。"""

        with path.open("rb") as f:
            raw = tomllib.load(f)

        # セクション名とSettingsクラスの対応をまとめてループで処理
        section_classes = {
            "youtube": YouTubeSettings,
            "video_edit": VideoEditSettings,
            "obs": OBSSettings,
            "image_matching": ImageMatchingSettings,
        }
        kwargs = {}
        for section, cls_ in section_classes.items():
            if section in raw:
                kwargs[section] = cls_(**raw[section])

        return cls(**kwargs)
