"""YouTube へのアップロードサービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.domain.models.upload_config import YouTubeUploadConfig
from splat_replay.domain.models.video_clip import VideoClip
from splat_replay.shared.logger import get_logger

logger = get_logger()


class YouTubeUploader:
    """YouTube API を用いて動画をアップロードする。"""

    def upload_video(
        self, clip: VideoClip, config: YouTubeUploadConfig
    ) -> str:
        """動画をアップロードし、動画 ID を返す。"""
        logger.info("動画アップロード", clip=str(clip.path))
        raise NotImplementedError

    def upload_thumbnail(self, video_id: str, thumbnail: Path) -> None:
        """サムネイルをアップロードする。"""
        logger.info(
            "サムネイルアップロード",
            video_id=video_id,
            thumbnail=str(thumbnail),
        )
        raise NotImplementedError

    def upload_subtitle(self, video_id: str, subtitle: Path) -> None:
        """字幕ファイルをアップロードする。"""
        logger.info(
            "字幕アップロード", video_id=video_id, subtitle=str(subtitle)
        )
        raise NotImplementedError

    def add_to_playlist(self, video_id: str, playlist_id: str) -> None:
        """動画を指定したプレイリストへ追加する。"""
        logger.info(
            "プレイリスト追加", video_id=video_id, playlist_id=playlist_id
        )
        raise NotImplementedError
