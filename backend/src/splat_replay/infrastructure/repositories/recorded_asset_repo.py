"""録画アセットの管理に特化したリポジトリ。"""

from __future__ import annotations

import shutil
from pathlib import Path

from structlog.stdlib import BoundLogger

from splat_replay.domain.config import VideoStorageSettings
from splat_replay.domain.models import Frame, RecordingMetadata, VideoAsset
from splat_replay.infrastructure.repositories.asset_file_operations import (
    AssetEventPublisher,
    AssetFileOperations,
)


class RecordedAssetRepository:
    """録画アセットの管理を担当するリポジトリ。

    このクラスは以下の責務のみを持つ：
    - 録画ファイルの保存・削除・一覧取得
    - 字幕/サムネイル/メタデータの操作
    - 録画関連のイベント発行
    """

    def __init__(
        self,
        settings: VideoStorageSettings,
        logger: BoundLogger,
        file_ops: AssetFileOperations,
        event_publisher: AssetEventPublisher,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self._file_ops = file_ops
        self._event_publisher = event_publisher

    def save_recording(
        self,
        video: Path,
        srt: Path | None,
        screenshot: Frame | None,
        metadata: RecordingMetadata,
    ) -> VideoAsset:
        """録画ファイルを保存する。

        Args:
            video: 動画ファイルパス
            srt: 字幕ファイルパス
            screenshot: スクリーンショット
            metadata: 録画メタデータ

        Returns:
            保存されたVideoAsset
        """
        dest = self.settings.recorded_dir
        dest.mkdir(parents=True, exist_ok=True)

        name_root = self._file_ops.generate_filename(metadata)
        base_path = dest / name_root
        target = base_path.with_suffix(video.suffix)
        moved_files: list[tuple[Path, Path]] = []
        created_files: list[Path] = []

        try:
            # 動画ファイルの移動
            source_video = video.resolve()
            shutil.move(str(source_video), target)
            moved_files.append((target, source_video))

            # 字幕ファイルの移動
            if srt is not None:
                source_subtitle = srt.resolve()
                subtitle_path = base_path.with_suffix(".srt")
                source_subtitle.rename(subtitle_path)
                moved_files.append((subtitle_path, source_subtitle))

            # スクリーンショットの保存
            if screenshot is not None:
                if not self._file_ops.save_thumbnail(base_path, screenshot):
                    raise RuntimeError("サムネイルの保存に失敗しました")
                created_files.append(base_path.with_suffix(".png"))

            # メタデータの保存
            if not self._file_ops.save_metadata(base_path, metadata):
                raise RuntimeError("メタデータの保存に失敗しました")
            created_files.append(base_path.with_suffix(".json"))
        except Exception:
            self._cleanup_created_files(created_files)
            self._rollback_moved_files(moved_files)
            raise

        self.logger.info("録画ファイル保存", path=str(target))

        # イベント発行
        self._event_publisher.publish_recorded_saved(
            video=target,
            has_subtitle=base_path.with_suffix(".srt").exists(),
            has_thumbnail=base_path.with_suffix(".png").exists(),
            started_at=metadata.started_at.isoformat()
            if metadata.started_at
            else None,
        )

        return VideoAsset(
            video=target,
            subtitle=base_path.with_suffix(".srt"),
            thumbnail=base_path.with_suffix(".png"),
            metadata=metadata,
        )

    def _cleanup_created_files(self, paths: list[Path]) -> None:
        """保存途中に作成したファイルを削除する。"""
        for path in reversed(paths):
            path.unlink(missing_ok=True)

    def _rollback_moved_files(self, paths: list[tuple[Path, Path]]) -> None:
        """保存途中に移動したファイルを元の場所へ戻す。"""
        for current_path, original_path in reversed(paths):
            if not current_path.exists() or original_path.exists():
                continue
            try:
                shutil.move(str(current_path), original_path)
            except Exception as exc:
                self.logger.warning(
                    "保存失敗時のロールバックに失敗しました",
                    current_path=str(current_path),
                    original_path=str(original_path),
                    error=str(exc),
                )

    def get_asset(self, video: Path) -> VideoAsset | None:
        """録画アセットを取得する。

        Args:
            video: 動画ファイルパス

        Returns:
            VideoAsset。メタデータが存在しない場合はNone
        """
        asset = self._load_asset(video)
        if asset.metadata is None:
            return None
        return asset

    def list_recordings(self) -> list[VideoAsset]:
        """録画アセットの一覧を取得する。

        Returns:
            VideoAssetのリスト
        """
        assets: list[VideoAsset] = []
        for pattern in ("*.mkv", "*.mp4"):
            for video in self.settings.recorded_dir.glob(pattern):
                assets.append(self._load_asset(video))
        return assets

    def _load_asset(self, video: Path) -> VideoAsset:
        """内部用：アセットを読み込む。

        Args:
            video: 動画ファイルパス

        Returns:
            VideoAsset
        """
        subtitle_candidate = video.with_suffix(".srt")
        subtitle: Path | None = (
            subtitle_candidate if subtitle_candidate.exists() else None
        )
        thumbnail_candidate = video.with_suffix(".png")
        thumbnail: Path | None = (
            thumbnail_candidate if thumbnail_candidate.exists() else None
        )
        metadata = self._file_ops.load_metadata(video)
        return VideoAsset(
            video=video,
            subtitle=subtitle,
            thumbnail=thumbnail,
            metadata=metadata,
        )

    def delete_recording(self, video: Path) -> bool:
        """録画ファイルを削除する。

        Args:
            video: 動画ファイルパス

        Returns:
            すべてのファイルが削除された場合True
        """
        video = video.resolve()
        if video.exists():
            video.unlink(missing_ok=True)

        self._file_ops.delete_related_files(video)

        self._event_publisher.publish_recorded_deleted(video)

        return (
            not video.exists()
            and not video.with_suffix(".srt").exists()
            and not video.with_suffix(".png").exists()
            and not video.with_suffix(".json").exists()
        )

    def get_subtitle(self, video: Path) -> str | None:
        """字幕を取得する。

        Args:
            video: 動画ファイルパス

        Returns:
            字幕内容。存在しない場合はNone
        """
        return self._file_ops.load_subtitle(video)

    def save_subtitle(self, video: Path, content: str) -> bool:
        """字幕を保存する。

        Args:
            video: 動画ファイルパス
            content: 字幕内容

        Returns:
            成功した場合True
        """
        success = self._file_ops.save_subtitle(video, content)
        if success:
            self._event_publisher.publish_recorded_subtitle_updated(video)
        return success

    def save_edited_metadata(
        self, video: Path, metadata: RecordingMetadata
    ) -> None:
        """メタデータを更新する。

        Args:
            video: 動画ファイルパス
            metadata: 更新するメタデータ
        """
        self._file_ops.save_metadata(video, metadata)
        self._event_publisher.publish_recorded_metadata_updated(video)
