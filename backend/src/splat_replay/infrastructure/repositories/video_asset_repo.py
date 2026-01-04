"""動画ファイルを保存・管理するリポジトリ実装。

このクラスはVideoAssetRepositoryPortの薄いラッパーとして機能し、
実際の処理はRecordedAssetRepositoryとEditedAssetRepositoryに委譲する。
Clean Architecture の原則に従い、ポート実装は薄く保つ。
"""

from __future__ import annotations

from pathlib import Path

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    DomainEventPublisher,
    VideoAssetRepositoryPort,
)
from splat_replay.application.interfaces.data import FileStats
from splat_replay.domain.config import VideoStorageSettings
from splat_replay.domain.models import Frame, RecordingMetadata, VideoAsset
from splat_replay.infrastructure.repositories.asset_file_operations import (
    AssetEventPublisher,
    AssetFileOperations,
)
from splat_replay.infrastructure.repositories.edited_asset_repo import (
    EditedAssetRepository,
)
from splat_replay.infrastructure.repositories.recorded_asset_repo import (
    RecordedAssetRepository,
)


class FileVideoAssetRepository(VideoAssetRepositoryPort):
    """ファイルシステム上でVideoAssetを管理する実装。

    このクラスはポートインターフェースの薄いラッパーであり、
    実際の処理は責務ごとに分離されたリポジトリに委譲する。
    """

    def __init__(
        self,
        settings: VideoStorageSettings,
        logger: BoundLogger,
        publisher: DomainEventPublisher,
    ) -> None:
        self.settings = settings
        self.logger = logger

        # 共通機能の初期化
        file_ops = AssetFileOperations(logger)
        event_publisher = AssetEventPublisher(publisher)

        # 録画・編集済みリポジトリの初期化
        self._recorded_repo = RecordedAssetRepository(
            settings, logger, file_ops, event_publisher
        )
        self._edited_repo = EditedAssetRepository(
            settings, logger, file_ops, event_publisher
        )

    def get_recorded_dir(self) -> Path:
        """録画ディレクトリを取得する。"""
        return self.settings.recorded_dir

    def get_edited_dir(self) -> Path:
        """編集済みディレクトリを取得する。"""
        return self.settings.edited_dir

    def save_recording(
        self,
        video: Path,
        srt: Path | None,
        screenshot: Frame | None,
        metadata: RecordingMetadata,
    ) -> VideoAsset:
        """録画ファイルを保存する（RecordedAssetRepositoryに委譲）。"""
        return self._recorded_repo.save_recording(
            video, srt, screenshot, metadata
        )

    def get_asset(self, video: Path) -> VideoAsset | None:
        """録画アセットを取得する（RecordedAssetRepositoryに委譲）。"""
        return self._recorded_repo.get_asset(video)

    def get_file_stats(self, video: Path) -> FileStats | None:
        """ファイル統計情報を取得する。"""
        try:
            stat = video.stat()
        except FileNotFoundError:
            return None
        return FileStats(size_bytes=stat.st_size, updated_at=stat.st_mtime)

    def has_subtitle(self, video: Path) -> bool:
        """字幕ファイルの存在を確認する。"""
        return video.with_suffix(".srt").exists()

    def has_thumbnail(self, video: Path) -> bool:
        """サムネイルファイルの存在を確認する。"""
        return video.with_suffix(".png").exists()

    def save_edited_metadata(
        self, video: Path, metadata: RecordingMetadata
    ) -> None:
        """録画メタデータを更新する（RecordedAssetRepositoryに委譲）。"""
        self._recorded_repo.save_edited_metadata(video, metadata)

    def list_recordings(self) -> list[VideoAsset]:
        """録画アセットの一覧を取得する（RecordedAssetRepositoryに委譲）。"""
        return self._recorded_repo.list_recordings()

    def delete_recording(self, video: Path) -> bool:
        """録画ファイルを削除する（RecordedAssetRepositoryに委譲）。"""
        return self._recorded_repo.delete_recording(video)

    def get_subtitle(self, video: Path) -> str | None:
        """録画の字幕を取得する（RecordedAssetRepositoryに委譲）。"""
        return self._recorded_repo.get_subtitle(video)

    def save_subtitle(self, video: Path, content: str) -> bool:
        """録画の字幕を保存する（RecordedAssetRepositoryに委譲）。"""
        return self._recorded_repo.save_subtitle(video, content)

    def save_edited(self, video: Path) -> Path:
        """編集済みファイルを保存する（EditedAssetRepositoryに委譲）。"""
        return self._edited_repo.save_edited(video)

    def list_edited(self) -> list[Path]:
        """編集済みファイルの一覧を取得する（EditedAssetRepositoryに委譲）。"""
        return self._edited_repo.list_edited()

    def delete_edited(self, video: Path) -> bool:
        """編集済みファイルを削除する（EditedAssetRepositoryに委譲）。"""
        return self._edited_repo.delete_edited(video)

    def get_edited_subtitle(self, video: Path) -> str | None:
        """編集済み動画の字幕を取得する（EditedAssetRepositoryに委譲）。"""
        return self._edited_repo.get_subtitle(video)

    def save_edited_subtitle(self, video: Path, content: str) -> bool:
        """編集済み動画の字幕を保存する（EditedAssetRepositoryに委譲）。"""
        return self._edited_repo.save_subtitle(video, content)

    def get_edited_thumbnail(self, video: Path) -> bytes | None:
        """編集済み動画のサムネイルを取得する（EditedAssetRepositoryに委譲）。"""
        return self._edited_repo.get_thumbnail(video)

    def save_edited_thumbnail(self, video: Path, data: bytes) -> bool:
        """編集済み動画のサムネイルを保存する（EditedAssetRepositoryに委譲）。"""
        return self._edited_repo.save_thumbnail(video, data)

    def get_edited_metadata(self, video: Path) -> dict[str, str] | None:
        """編集済み動画のメタデータを取得する（EditedAssetRepositoryに委譲）。"""
        return self._edited_repo.get_metadata(video)

    def save_edited_metadata_dict(
        self, video: Path, metadata: dict[str, str]
    ) -> bool:
        """編集済み動画のメタデータを保存する（EditedAssetRepositoryに委譲）。"""
        return self._edited_repo.save_metadata(video, metadata)
