import asyncio
from pathlib import Path
from typing import Optional

from splat_replay.application.interfaces.common import (
    ConfigPort,
    FileSystemPort,
    LoggerPort,
)
from splat_replay.application.interfaces.data import (
    Caption,
    UploadSettingsView,
)
from splat_replay.application.interfaces.upload import UploadPort
from splat_replay.application.interfaces.video import (
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.application.services.common.progress import ProgressReporter


class AutoUploader:
    """編集済動画をアップロードするサービス"""

    def __init__(
        self,
        uploader: UploadPort,
        video_editor: VideoEditorPort,
        config: ConfigPort,
        repo: VideoAssetRepositoryPort,
        logger: LoggerPort,
        file_system: FileSystemPort,
        progress: ProgressReporter,
    ) -> None:
        self.repo = repo
        self.logger = logger
        self.uploader = uploader
        self.video_editor = video_editor
        self.config = config
        self._file_system = file_system
        self._cached_settings: Optional[UploadSettingsView] = None
        self.progress = progress
        self._cancelled: bool = False

    @property
    def _settings(self) -> UploadSettingsView:
        """設定を取得（キャッシュあり）。"""
        if self._cached_settings is None:
            self._cached_settings = self.config.get_upload_settings()
        return self._cached_settings

    def update_settings(self, settings: UploadSettingsView) -> None:
        """設定を更新する。

        Args:
            settings: 新しい設定
        """
        self._cached_settings = settings
        self.logger.info(
            "Upload settings updated", privacy_status=settings.privacy_status
        )

    def set_privacy_status(self, privacy_status: str) -> None:
        """YouTube公開設定を保存する。"""
        # 設定を読み込んで新しいprivacy_statusで保存
        self.config.save_upload_privacy_status(privacy_status)
        self._cached_settings = self.config.get_upload_settings()
        self.logger.info(
            "YouTube privacy status saved", privacy_status=privacy_status
        )

    def request_cancel(self) -> None:
        """実行中のアップロードへキャンセルを要求する。"""
        self._cancelled = True

    def reset_cancel(self) -> None:
        """新しい実行の開始前にキャンセル状態を初期化する。"""
        self._cancelled = False

    def _raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise asyncio.CancelledError

    def _finish_cancelled(self, task_id: str) -> None:
        self.progress.finish(
            task_id, False, "自動アップロードをキャンセルしました"
        )
        self.logger.info("自動アップロードをキャンセルしました")

    async def execute(self) -> None:
        self.logger.info("自動アップロードを開始します")
        self._cached_settings = self.config.get_upload_settings()

        videos = self.repo.list_edited()

        task_id = "auto_upload"
        items: list[str] = []
        for video in videos:
            self._raise_if_cancelled()
            metadata = await self.video_editor.get_metadata(video)
            self._raise_if_cancelled()
            items.append(metadata.get("title", video.name))
        self.progress.start_task(
            task_id, "アップロード準備", len(items), items=items
        )
        for idx, video in enumerate(videos):
            if self._cancelled:
                self._finish_cancelled(task_id)
                return

            self.logger.info("アップロード中", path=str(video))

            try:
                await self._upload(idx, video)
            except asyncio.CancelledError:
                self._finish_cancelled(task_id)
                return
            self.progress.item_stage(task_id, idx, "delete", "ファイル削除中")
            if not self.repo.delete_edited(video):
                raise RuntimeError(
                    f"アップロード済み動画を削除できませんでした: {video}"
                )

            self.progress.advance(task_id)
            if self._cancelled:
                self._finish_cancelled(task_id)
                return

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
            self._raise_if_cancelled()

            # サムネイルをリポジトリ経由で読み込む
            thumb_data = self.repo.get_edited_thumbnail(path)
            if thumb_data:
                temp_thumb = path.with_suffix(".tmp.png")
                await asyncio.to_thread(
                    self._file_system.write_bytes, temp_thumb, thumb_data
                )
                self._raise_if_cancelled()

            # 字幕をリポジトリ経由で読み込む
            srt_content = self.repo.get_edited_subtitle(path)
            if srt_content:
                temp_subtitle = path.with_suffix(".tmp.srt")
                await asyncio.to_thread(
                    self._file_system.write_text,
                    temp_subtitle,
                    srt_content,
                    "utf-8",
                )
                self._raise_if_cancelled()

            self.progress.item_stage(
                task_id,
                idx,
                "upload",
                "アップロード中",
                message=path.name,
            )

            def on_progress(percent: float) -> None:
                self.progress.progress(task_id, percent)

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
                progress_callback=on_progress,
                cancel_check=lambda: self._cancelled,
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
                await asyncio.to_thread(
                    self._file_system.unlink, temp_thumb, missing_ok=True
                )
            if temp_subtitle:
                await asyncio.to_thread(
                    self._file_system.unlink, temp_subtitle, missing_ok=True
                )
