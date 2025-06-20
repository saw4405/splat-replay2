"""動画編集サービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.domain.models.edit_config import VideoEditConfig
from splat_replay.domain.models.match import Match
from splat_replay.domain.models.video_clip import VideoClip


class VideoEditor:
    """FFmpeg 等を用いた動画編集処理を提供する。"""

    def process(self, path: Path) -> Path:
        """動画編集のメインエントリーポイント。"""
        return path

    def merge_clips(self, clips: list[VideoClip]) -> VideoClip:
        """複数のクリップを結合して新しいクリップを作成する。"""
        raise NotImplementedError

    def embed_metadata(self, clip: VideoClip, match: Match) -> None:
        """メタデータを動画に書き込む。"""
        raise NotImplementedError

    def adjust_volume(self, clip: VideoClip, config: VideoEditConfig) -> None:
        """音量を調整する。"""
        raise NotImplementedError

    def generate_thumbnail(self, clip: VideoClip) -> Path:
        """サムネイル画像を生成する。"""
        raise NotImplementedError

    def embed_subtitle(self, clip: VideoClip, subtitle: Path) -> None:
        """字幕を動画に埋め込む。"""
        raise NotImplementedError
