"""編集済みアセットの管理に特化したリポジトリ。"""

from __future__ import annotations

import shutil
from pathlib import Path

from structlog.stdlib import BoundLogger

from splat_replay.domain.config import VideoStorageSettings
from splat_replay.infrastructure.repositories.asset_file_operations import (
    AssetEventPublisher,
    AssetFileOperations,
)


class EditedAssetRepository:
    """編集済みアセットの管理を担当するリポジトリ。

    このクラスは以下の責務のみを持つ：
    - 編集済みファイルの保存・削除・一覧取得
    - 字幕/サムネイル/メタデータの操作
    - 編集済み関連のイベント発行
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

    def save_edited(self, video: Path) -> Path:
        """編集済みファイルを保存する。

        Args:
            video: 動画ファイルパス

        Returns:
            保存先パス
        """
        dest = self.settings.edited_dir
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / video.name

        # 動画ファイルを移動
        try:
            shutil.move(str(video), target)
        except Exception:
            target = video

        # 関連ファイル（字幕、サムネイル、メタデータ）も移動
        for suffix in (".srt", ".png", ".json"):
            src_file = video.with_suffix(suffix)
            if src_file.exists():
                dst_file = target.with_suffix(suffix)
                try:
                    shutil.move(str(src_file), dst_file)
                    self.logger.info(
                        f"関連ファイル{suffix}を移動しました",
                        src=str(src_file),
                        dst=str(dst_file),
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.error(
                        f"関連ファイル{suffix}の移動に失敗しました",
                        error=str(exc),
                        src=str(src_file),
                    )

        self.logger.info("編集後ファイル保存", path=str(target))

        self._event_publisher.publish_edited_saved(target)
        return target

    def list_edited(self) -> list[Path]:
        """編集済みファイルの一覧を取得する。

        Returns:
            ファイルパスのリスト
        """
        videos: list[Path] = []
        for pattern in ("*.mkv", "*.mp4"):
            videos.extend(self.settings.edited_dir.glob(pattern))
        return videos

    def delete_edited(self, video: Path) -> bool:
        """編集済みファイルを削除する。

        Args:
            video: 動画ファイルパス

        Returns:
            すべてのファイルが削除された場合True
        """
        video = video.resolve()
        if video.exists():
            video.unlink(missing_ok=True)

        self._file_ops.delete_related_files(video)

        self._event_publisher.publish_edited_deleted(video)

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
        return self._file_ops.save_subtitle(video, content)

    def get_thumbnail(self, video: Path) -> bytes | None:
        """サムネイルを取得する。

        Args:
            video: 動画ファイルパス

        Returns:
            サムネイルデータ。存在しない場合はNone
        """
        return self._file_ops.load_thumbnail(video)

    def save_thumbnail(self, video: Path, data: bytes) -> bool:
        """サムネイルを保存する。

        Args:
            video: 動画ファイルパス
            data: サムネイルデータ

        Returns:
            成功した場合True
        """
        return self._file_ops.save_thumbnail(video, data)

    def get_metadata(self, video: Path) -> dict[str, str] | None:
        """メタデータを取得する。

        Args:
            video: 動画ファイルパス

        Returns:
            メタデータ辞書。存在しない場合はNone
        """
        return self._file_ops.load_metadata_dict(video)

    def save_metadata(self, video: Path, metadata: dict[str, str]) -> bool:
        """メタデータを保存する。

        Args:
            video: 動画ファイルパス
            metadata: メタデータ辞書

        Returns:
            成功した場合True
        """
        return self._file_ops.save_metadata(video, metadata)
