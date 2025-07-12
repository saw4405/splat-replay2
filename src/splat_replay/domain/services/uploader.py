"""YouTube へのアップロードサービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import UploadPort
from splat_replay.infrastructure.adapters.ffmpeg_processor import FFmpegProcessor
from splat_replay.infrastructure.adapters.youtube_client import YouTubeClient
from splat_replay.shared.config import YouTubeSettings
from splat_replay.shared.logger import get_logger

logger = get_logger()


class YouTubeUploader(UploadPort):
    """YouTube API を用いて動画をアップロードする。"""

    def __init__(self, client: YouTubeClient, ffmpeg: FFmpegProcessor, settings: YouTubeSettings) -> None:
        self.client = client
        self.ffmpeg = ffmpeg
        self.settings = settings

    def upload(self, path: Path) -> str:
        """動画をアップロードし、動画 ID を返す。"""
        logger.info("動画アップロード", clip=str(path))

        metadata = self.ffmpeg.get_metadata(path)

        id = self.client.upload(
            path,
            title=metadata.get("title", ""),
            description=metadata.get("comment", ""),
            tags=self.settings.tags or [],
            privacy_status=self.settings.privacy_status,
        )
        logger.info("動画アップロード完了", video_id=id)

        if not id:
            return ""

        thumb_data = self.ffmpeg.get_thumbnail(path)
        if thumb_data:
            thumb = path.with_suffix(".png")
            thumb.write_bytes(thumb_data)
            self.client.upload_thumbnail(id, thumb)
            thumb.unlink(missing_ok=True)
            logger.info("サムネイルアップロード完了", video_id=id)

        srt = self.ffmpeg.get_subtitle(path)
        if srt:
            subtitle = path.with_suffix(".srt")
            subtitle.write_text(srt, encoding="utf-8")
            self.client.upload_subtitle(
                id, subtitle, self.settings.caption_name)
            subtitle.unlink(missing_ok=True)
            logger.info("字幕アップロード完了", video_id=id)

        if self.settings.playlist_id:
            self.client.add_to_playlist(id, self.settings.playlist_id)
            logger.info("プレイリストに追加完了", video_id=id)

        return id
