from pathlib import Path
from typing import Optional

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    Caption,
    UploadPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.shared.config import UploadSettings

from .progress import ProgressReporter


class AutoUploader:
    """編集済動画をアップロードするサービス"""

    def __init__(
        self,
        uploader: UploadPort,
        video_editor: VideoEditorPort,
        settings: UploadSettings,
        repo: VideoAssetRepositoryPort,
        logger: BoundLogger,
        progress: ProgressReporter,
    ) -> None:
        self.repo = repo
        self.logger = logger
        self.uploader = uploader
        self.video_editor = video_editor
        self.settings = settings
        self.progress = progress
        self._cancelled: bool = False

    def request_cancel(self) -> None:
        """Request cancellation; effective between items/steps."""
        self._cancelled = True

    async def execute(self):
        self.logger.info("自動アップロードを開始します")

        videos = self.repo.list_edited()

        task_id = "auto_upload"
        items: list[str] = [
            self.video_editor.get_metadata(v).get("title", v.name)
            for v in videos
        ]
        self.progress.start_task(
            task_id, "アップロード準備", len(items), items=items
        )
        for idx, video in enumerate(videos):
            if self._cancelled:
                self.progress.finish(
                    task_id, False, "自動アップロードをキャンセルしました"
                )
                self.logger.info("自動アップロードをキャンセルしました")
                return

            self.logger.info("アップロード中", path=str(video))

            self._upload(idx, video)
            self.progress.item_stage(task_id, idx, "delete", "ファイル削除中")
            self.repo.delete_edited(video)

            self.progress.advance(task_id)

        self.progress.finish(task_id, True, "自動アップロードを完了しました")
        self.logger.info("自動アップロードを完了しました")

    def _upload(self, idx: int, path: Path):
        """動画をアップロードし、動画 ID を返す"""
        self.logger.info("動画アップロード中", clip=str(path))

        task_id = "auto_upload"
        thumb: Optional[Path] = None
        subtitle: Optional[Path] = None

        try:
            self.progress.item_stage(
                task_id, idx, "collect", "ファイル情報収集中"
            )
            metadata = self.video_editor.get_metadata(path)

            thumb_data = self.video_editor.get_thumbnail(path)
            if thumb_data:
                thumb = path.with_suffix(".png")
                thumb.write_bytes(thumb_data)

            srt = self.video_editor.get_subtitle(path)
            if srt:
                subtitle = path.with_suffix(".srt")
                subtitle.write_text(srt, encoding="utf-8")

            self.progress.item_stage(
                task_id,
                idx,
                "upload",
                "アップロード中",
                message=path.name,
            )
            self.uploader.upload(
                path,
                title=metadata.get("title", ""),
                description=metadata.get("comment", ""),
                tags=self.settings.tags,
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
            self.logger.info("動画アップロードを完了しました")
            if subtitle:
                self.progress.item_stage(
                    task_id,
                    idx,
                    "caption",
                    "字幕アップロード中",
                    message=subtitle.name,
                )
            if thumb:
                self.progress.item_stage(
                    task_id,
                    idx,
                    "thumb",
                    "サムネイルアップロード中",
                    message=thumb.name,
                )
            self.progress.item_stage(
                task_id,
                idx,
                "playlist",
                "プレイリスト追加中",
                message=path.name,
            )
            # deprecated: external UPLOADER_ITEM_FINISHED removed
        finally:
            if thumb:
                thumb.unlink(missing_ok=True)

            if subtitle:
                subtitle.unlink(missing_ok=True)
