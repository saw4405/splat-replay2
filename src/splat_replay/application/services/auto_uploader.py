from pathlib import Path
from typing import Optional

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    Caption,
    UploadPort,
    VideoAssetRepository,
    VideoEditorPort,
)
from splat_replay.shared.config import UploadSettings


class AutoUploader:
    """編集済み動画をアップロードするサービス。"""

    def __init__(
        self,
        uploader: UploadPort,
        video_editor: VideoEditorPort,
        settings: UploadSettings,
        repo: VideoAssetRepository,
        logger: BoundLogger,
    ):
        self.repo = repo
        self.logger = logger
        self.uploader = uploader
        self.video_editor = video_editor
        self.settings = settings

    async def execute(self):
        self.logger.info("自動アップロード開始")
        for video in self.repo.list_edited():
            self.logger.info("アップロード", path=str(video))
            self._upload(video)
            self.repo.delete_edited(video)

        self.logger.info("自動アップロード終了")

    def _upload(self, path: Path):
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
