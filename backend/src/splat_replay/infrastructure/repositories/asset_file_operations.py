"""録画アセット管理のリポジトリ実装。"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import DomainEventPublisher
from splat_replay.domain.events import (
    AssetEditedDeleted,
    AssetEditedSaved,
    AssetRecordedDeleted,
    AssetRecordedMetadataUpdated,
    AssetRecordedSaved,
    AssetRecordedSubtitleUpdated,
)
from splat_replay.domain.models import BattleResult, Frame, RecordingMetadata


class AssetFileOperations:
    """アセットファイル操作の共通ロジック。

    このクラスは以下の責務のみを持つ：
    - ファイル名生成
    - 関連ファイル（字幕/サムネイル/メタデータ）の読み書き
    - ファイルパス管理
    """

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger

    def generate_filename(self, metadata: RecordingMetadata) -> str:
        """メタデータから統一的なファイル名を生成する。

        Args:
            metadata: 録画メタデータ

        Returns:
            拡張子を除いたファイル名
        """
        if metadata.started_at is None:
            raise ValueError("Metadata must have a started_at timestamp")

        if isinstance(metadata.result, BattleResult):
            return "_".join(
                [
                    metadata.started_at.strftime("%Y%m%d_%H%M%S"),
                    metadata.result.match.value,
                    metadata.result.rule.value,
                    metadata.judgement.value if metadata.judgement else "",
                    metadata.result.stage.value,
                ]
            )
        return metadata.started_at.strftime("%Y%m%d_%H%M%S")

    def save_subtitle(self, base_path: Path, content: str) -> bool:
        """字幕ファイルを保存する。

        Args:
            base_path: 動画ファイルパス
            content: 字幕内容

        Returns:
            成功した場合True
        """
        subtitle = base_path.with_suffix(".srt")
        try:
            subtitle.parent.mkdir(parents=True, exist_ok=True)
            subtitle.write_text(content, encoding="utf-8")
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "字幕の保存に失敗しました", path=str(subtitle), error=str(exc)
            )
            return False

    def load_subtitle(self, base_path: Path) -> str | None:
        """字幕ファイルを読み込む。

        Args:
            base_path: 動画ファイルパス

        Returns:
            字幕内容。ファイルが存在しない場合はNone
        """
        subtitle = base_path.with_suffix(".srt")
        if not subtitle.exists():
            return None
        try:
            return subtitle.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "字幕の読み込みに失敗しました",
                path=str(subtitle),
                error=str(exc),
            )
            return None

    def save_thumbnail(self, base_path: Path, data: bytes | Frame) -> bool:
        """サムネイルファイルを保存する。

        Args:
            base_path: 動画ファイルパス
            data: サムネイルデータ（バイトまたはnumpy配列）

        Returns:
            成功した場合True
        """
        thumbnail = base_path.with_suffix(".png")
        try:
            thumbnail.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(data, (bytes, bytearray)):
                thumbnail.write_bytes(bytes(data))
                return True
            success, buf = cv2.imencode(".png", data)
            if not success:
                self.logger.error(
                    "Thumbnail encoding failed", path=str(thumbnail)
                )
                return False
            with open(thumbnail, "wb") as f:
                f.write(buf.tobytes())
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "サムネイルの保存に失敗しました",
                path=str(thumbnail),
                error=str(exc),
            )
            return False

    def load_thumbnail(self, base_path: Path) -> bytes | None:
        """サムネイルファイルを読み込む。

        Args:
            base_path: 動画ファイルパス

        Returns:
            サムネイルデータ。ファイルが存在しない場合はNone
        """
        thumbnail = base_path.with_suffix(".png")
        if not thumbnail.exists():
            return None
        try:
            return thumbnail.read_bytes()
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "サムネイルの読み込みに失敗しました",
                path=str(thumbnail),
                error=str(exc),
            )
            return None

    def save_metadata(
        self, base_path: Path, metadata: RecordingMetadata | dict[str, str]
    ) -> bool:
        """メタデータファイルを保存する。

        Args:
            base_path: 動画ファイルパス
            metadata: メタデータ（RecordingMetadata または辞書）

        Returns:
            成功した場合True
        """
        metadata_path = base_path.with_suffix(".json")
        try:
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(metadata, RecordingMetadata):
                data = metadata.to_dict()
            else:
                data = metadata
            metadata_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "メタデータの保存に失敗しました",
                path=str(metadata_path),
                error=str(exc),
            )
            return False

    def load_metadata(self, base_path: Path) -> RecordingMetadata | None:
        """メタデータファイルを読み込む。

        Args:
            base_path: 動画ファイルパス

        Returns:
            メタデータ。ファイルが存在しない場合はNone
        """
        metadata_path = base_path.with_suffix(".json")
        if not metadata_path.exists():
            return None
        try:
            from splat_replay.application.services.editing.metadata_parser import (
                MetadataParser,
            )

            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            return MetadataParser.from_dict(data)
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "メタデータの読み込みに失敗しました",
                path=str(metadata_path),
                error=str(exc),
            )
            return None

    def load_metadata_dict(self, base_path: Path) -> dict[str, str] | None:
        """メタデータファイルを辞書として読み込む。

        Args:
            base_path: 動画ファイルパス

        Returns:
            メタデータ辞書。ファイルが存在しない場合はNone
        """
        metadata_path = base_path.with_suffix(".json")
        if not metadata_path.exists():
            return None
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            return {
                str(k): str(v) if v is not None else ""
                for k, v in data.items()
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "メタデータの読み込みに失敗しました",
                path=str(metadata_path),
                error=str(exc),
            )
            return None

    def delete_related_files(self, base_path: Path) -> None:
        """関連ファイル（字幕/サムネイル/メタデータ）を削除する。

        Args:
            base_path: 動画ファイルパス
        """
        for suffix in (".srt", ".png", ".json"):
            file_path = base_path.with_suffix(suffix)
            if file_path.exists():
                file_path.unlink(missing_ok=True)


class AssetEventPublisher:
    """アセット操作のイベント発行を担当するクラス。

    このクラスは以下の責務のみを持つ：
    - アセット操作イベントの発行
    - イベントデータの構築
    """

    def __init__(self, publisher: DomainEventPublisher) -> None:
        self._publisher = publisher

    def publish_recorded_saved(
        self,
        video: Path,
        has_subtitle: bool,
        has_thumbnail: bool,
        started_at: str | None,
    ) -> None:
        """録画保存イベントを発行する。"""
        import structlog

        logger = structlog.get_logger()
        logger.info(
            "ASSET_RECORDED_SAVED イベント発行",
            video=str(video),
            has_subtitle=has_subtitle,
            has_thumbnail=has_thumbnail,
        )
        self._publisher.publish_domain_event(
            AssetRecordedSaved(
                video=str(video),
                has_subtitle=has_subtitle,
                has_thumbnail=has_thumbnail,
                started_at=started_at,
            )
        )

    def publish_recorded_deleted(self, video: Path) -> None:
        """録画削除イベントを発行する。"""
        self._publisher.publish_domain_event(
            AssetRecordedDeleted(video=str(video))
        )

    def publish_recorded_metadata_updated(self, video: Path) -> None:
        """録画メタデータ更新イベントを発行する。"""
        self._publisher.publish_domain_event(
            AssetRecordedMetadataUpdated(video=str(video))
        )

    def publish_recorded_subtitle_updated(self, video: Path) -> None:
        """録画字幕更新イベントを発行する。"""
        self._publisher.publish_domain_event(
            AssetRecordedSubtitleUpdated(video=str(video))
        )

    def publish_edited_saved(self, video: Path) -> None:
        """編集済み保存イベントを発行する。"""
        self._publisher.publish_domain_event(
            AssetEditedSaved(video=str(video))
        )

    def publish_edited_deleted(self, video: Path) -> None:
        """編集済み削除イベントを発行する。"""
        self._publisher.publish_domain_event(
            AssetEditedDeleted(video=str(video))
        )
