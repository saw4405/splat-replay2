from pathlib import Path
from typing import Optional

from splat_replay.shared.config import UploadSettings
from structlog.stdlib import BoundLogger
from splat_replay.application.interfaces import (
    UploadPort,
    VideoEditorPort,
    Caption,
)


class Uploader:
    """動画をアップロードする。"""

    def __init__(
        self,
        uploader: UploadPort,
        video_editor: VideoEditorPort,
        settings: UploadSettings,
        logger: BoundLogger,
    ) -> None:
        self.uploader = uploader
        self.video_editor = video_editor
        self.settings = settings
        self.logger = logger

    def process(self, path: Path):
        """動画をアップロードし、動画 ID を返す。"""
        self.logger.info("動画アップロード", clip=str(path))

        thumb: Optional[Path] = None
        subtitle: Optional[Path] = None

        try:
            metadata = self.video_editor.get_metadata(path)

            thumb_data = self.video_editor.get_thumbnail(path)
            if thumb_data:
                thumb = path.with_suffix(".png")
                thumb.write_bytes(thumb_data)

            srt = self.video_editor.get_subtitle(path)
            if srt:
                subtitle = path.with_suffix(".srt")
                subtitle.write_text(srt, encoding="utf-8")

            self.uploader.upload(
                path,
                title=metadata.get("title", ""),
                description=metadata.get("comment", ""),
                tags=self.settings.tags or [],
                privacy_status=self.settings.privacy_status,
                thumb=thumb,
                caption=Caption(
                    subtitle=subtitle,
                    caption_name=self.settings.caption_name,
                )
                if subtitle
                else None,
                playlist_id=self.settings.playlist_id,
            )
            self.logger.info("動画アップロード完了", video_id=id)
        finally:
            if thumb:
                thumb.unlink(missing_ok=True)

            if subtitle:
                subtitle.unlink(missing_ok=True)
