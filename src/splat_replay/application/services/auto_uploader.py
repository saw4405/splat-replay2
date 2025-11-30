import asyncio
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
        self._settings = settings
        self.progress = progress
        self._cancelled: bool = False

    def update_settings(self, settings: UploadSettings) -> None:
        """設定を更新する。

        Args:
            settings: 新しい設定
        """
        self._settings = settings
        self.logger.info(
            "Upload settings updated", privacy_status=settings.privacy_status
        )

    def request_cancel(self) -> None:
        """キャンセル要求。アイテム/ステップ間で有効。"""
        self._cancelled = True

    async def execute(self) -> None:
        self.logger.info("自動アップロードを開始します")

        videos = self.repo.list_edited()

        task_id = "auto_upload"
        items: list[str] = []
        for video in videos:
            metadata = await self.video_editor.get_metadata(video)
            items.append(metadata.get("title", video.name))
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

            await self._upload(idx, video)
            self.progress.item_stage(task_id, idx, "delete", "ファイル削除中")
            self.repo.delete_edited(video)

            self.progress.advance(task_id)

        self.progress.finish(task_id, True, "自動アップロードを完了しました")
        self.logger.info("自動アップロードを完了しました")

    async def _upload(self, idx: int, path: Path) -> None:
        """動画をアップロードし、動画 ID を返す"""
        self.logger.info("動画アップロード中", clip=str(path))

        task_id = "auto_upload"
        temp_thumb: Optional[Path] = None
        temp_subtitle: Optional[Path] = None

        try:
            self.progress.item_stage(
                task_id, idx, "collect", "ファイル情報収集中"
            )

            # メタデータをリポジトリ経由で読み込む
            metadata = self.repo.get_edited_metadata(path) or {}

            # サムネイルをリポジトリ経由で読み込む
            thumb_data = self.repo.get_edited_thumbnail(path)
            if thumb_data:
                temp_thumb = path.with_suffix(".tmp.png")
                temp_thumb.write_bytes(thumb_data)

            # 字幕をリポジトリ経由で読み込む
            srt_content = self.repo.get_edited_subtitle(path)
            if srt_content:
                temp_subtitle = path.with_suffix(".tmp.srt")
                temp_subtitle.write_text(srt_content, encoding="utf-8")

            self.progress.item_stage(
                task_id,
                idx,
                "upload",
                "アップロード中",
                message=path.name,
            )
            await asyncio.to_thread(
                self.uploader.upload,
                path,
                title=metadata.get("title", ""),
                description=metadata.get("description", ""),
                tags=self._settings.tags,
                privacy_status=self._settings.privacy_status,
                thumb=temp_thumb,
                caption=Caption(
                    subtitle=temp_subtitle,
                    caption_name=self._settings.caption_name,
                )
                if temp_subtitle
                else None,
                playlist_id=self._settings.playlist_id,
            )
            self.logger.info("動画アップロードを完了しました")
            if temp_subtitle:
                self.progress.item_stage(
                    task_id,
                    idx,
                    "caption",
                    "字幕アップロード中",
                    message=temp_subtitle.name,
                )
            if temp_thumb:
                self.progress.item_stage(
                    task_id,
                    idx,
                    "thumb",
                    "サムネイルアップロード中",
                    message=temp_thumb.name,
                )
            self.progress.item_stage(
                task_id,
                idx,
                "playlist",
                "プレイリスト追加中",
                message=path.name,
            )
        finally:
            # 一時ファイルを削除
            if temp_thumb:
                temp_thumb.unlink(missing_ok=True)
            if temp_subtitle:
                temp_subtitle.unlink(missing_ok=True)
