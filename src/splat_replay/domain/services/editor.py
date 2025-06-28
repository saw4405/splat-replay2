"""動画編集サービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.domain.models.edit_config import VideoEditConfig
from splat_replay.domain.models.play import Play
from splat_replay.domain.models.video_clip import VideoClip
from splat_replay.shared.logger import get_logger

logger = get_logger()


class VideoEditor:
    """FFmpeg 等を用いた動画編集処理を提供する。"""

    def process(self, path: Path) -> Path:
        """動画編集のメインエントリーポイント。"""
        logger.info("動画編集開始", path=str(path))
        return path

    def merge_clips(self, clips: list[VideoClip]) -> VideoClip:
        """複数のクリップを結合して新しいクリップを作成する。"""
        logger.info("クリップ結合", clips=[c.path.name for c in clips])
        raise NotImplementedError

    def embed_metadata(self, clip: VideoClip, match: Play) -> None:
        """メタデータを動画に書き込む。"""
        logger.info("メタデータ書き込み", clip=str(clip.path))
        raise NotImplementedError

    def adjust_volume(self, clip: VideoClip, config: VideoEditConfig) -> None:
        """音量を調整する。"""
        logger.info("音量調整", clip=str(clip.path))
        raise NotImplementedError

    def generate_thumbnail(self, clip: VideoClip) -> Path:
        """サムネイル画像を生成する。"""
        logger.info("サムネイル生成", clip=str(clip.path))
        raise NotImplementedError

    def embed_subtitle(self, clip: VideoClip, subtitle: Path) -> None:
        """字幕を動画に埋め込む。"""
        logger.info(
            "字幕埋め込み", clip=str(clip.path), subtitle=str(subtitle)
        )
        raise NotImplementedError
