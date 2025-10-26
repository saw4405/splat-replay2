"""動画ファイルを保存・管理するリポジトリ実装."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from structlog.stdlib import BoundLogger

from splat_replay.application.events.types import EventTypes
from splat_replay.application.interfaces import (
    EventPublisher,
    VideoAssetRepositoryPort,
)
from splat_replay.domain.models import (
    BattleResult,
    RecordingMetadata,
    VideoAsset,
)
from splat_replay.shared.config import VideoStorageSettings


class FileVideoAssetRepository(VideoAssetRepositoryPort):
    """ファイルシステム上で VideoAsset を管理する実装."""

    def __init__(
        self,
        settings: VideoStorageSettings,
        logger: BoundLogger,
        publisher: EventPublisher,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self._publisher = publisher

    def get_recorded_dir(self) -> Path:
        return self.settings.recorded_dir

    def get_edited_dir(self) -> Path:
        return self.settings.edited_dir

    def save_recording(
        self,
        video: Path,
        srt: Path | None,
        screenshot: np.ndarray | None,
        metadata: RecordingMetadata,
    ) -> VideoAsset:
        if metadata.started_at is None:
            raise ValueError("Metadata must have a started_at timestamp")

        dest = self.settings.recorded_dir
        dest.mkdir(parents=True, exist_ok=True)
        if isinstance(metadata.result, BattleResult):
            name_root = "_".join(
                [
                    metadata.started_at.strftime("%Y%m%d_%H%M%S"),
                    metadata.result.match.value,
                    metadata.result.rule.value,
                    metadata.judgement.value if metadata.judgement else "",
                    metadata.result.stage.value,
                ]
            )
        else:
            name_root = metadata.started_at.strftime("%Y%m%d_%H%M%S")

        if srt is not None:
            srt = srt.resolve()
            srt.rename(dest / f"{name_root}.srt")

        target = dest / f"{name_root}{video.suffix}"
        try:
            shutil.move(str(video), target)
        except Exception:
            target = video
        if screenshot is not None:
            png_path = dest / f"{name_root}.png"
            success, buf = cv2.imencode(".png", screenshot)
            if success:
                with open(png_path, "wb") as f:
                    f.write(buf.tobytes())

        (dest / f"{name_root}.json").write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        self.logger.info("録画ファイル保存", path=str(target))

        self._publisher.publish(
            EventTypes.ASSET_RECORDED_SAVED,
            {
                "video": str(target),
                "has_subtitle": (dest / f"{name_root}.srt").exists(),
                "has_thumbnail": (dest / f"{name_root}.png").exists(),
                "started_at": metadata.started_at.isoformat()
                if metadata.started_at
                else None,
            },
        )

        return VideoAsset(
            video=target,
            subtitle=dest / f"{name_root}.srt",
            thumbnail=dest / f"{name_root}.png",
            metadata=metadata,
        )

    def get_asset(self, video: Path) -> VideoAsset | None:
        metadata_path = video.with_suffix(".json")
        if not metadata_path.exists():
            return None
        metadata = RecordingMetadata.from_dict(
            json.loads(metadata_path.read_text(encoding="utf-8"))
        )
        return VideoAsset(
            video=video,
            subtitle=video.with_suffix(".srt"),
            thumbnail=video.with_suffix(".png"),
            metadata=metadata,
        )

    def save_edited_metadata(
        self, video: Path, metadata: RecordingMetadata
    ) -> None:
        metadata_path = video.with_suffix(".json")
        metadata_path.write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )

        self._publisher.publish(
            EventTypes.ASSET_RECORDED_METADATA_UPDATED,
            {"video": str(video)},
        )

    def list_recordings(self) -> list[VideoAsset]:
        assets: list[VideoAsset] = []
        # Support common containers produced by OBS (mkv/mp4)
        for pattern in ("*.mkv", "*.mp4"):
            for video in self.settings.recorded_dir.glob(pattern):
                assets.append(VideoAsset.load(video))
        return assets

    def delete_recording(self, video: Path) -> bool:
        video = video.resolve()
        if video.exists():
            video.unlink(missing_ok=True)
        subtitle = video.with_suffix(".srt")
        if subtitle.exists():
            subtitle.unlink(missing_ok=True)
        thumbnail = video.with_suffix(".png")
        if thumbnail.exists():
            thumbnail.unlink(missing_ok=True)
        metadata = video.with_suffix(".json")
        if metadata.exists():
            metadata.unlink(missing_ok=True)

        self._publisher.publish(
            EventTypes.ASSET_RECORDED_DELETED,
            {"video": str(video)},
        )

        return (
            not video.exists()
            and not subtitle.exists()
            and not thumbnail.exists()
            and not metadata.exists()
        )

    def get_subtitle(self, video: Path) -> str | None:
        subtitle = video.with_suffix(".srt")
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

    def save_subtitle(self, video: Path, content: str) -> bool:
        subtitle = video.with_suffix(".srt")
        try:
            subtitle.parent.mkdir(parents=True, exist_ok=True)
            subtitle.write_text(content, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "字幕の保存に失敗しました", path=str(subtitle), error=str(exc)
            )
            return False

        self._publisher.publish(
            EventTypes.ASSET_RECORDED_SUBTITLE_UPDATED,
            {"video": str(video)},
        )
        return True

    def save_edited(self, video: Path) -> Path:
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

        self._publisher.publish(
            EventTypes.ASSET_EDITED_SAVED, {"video": str(target)}
        )
        return target

    def list_edited(self) -> list[Path]:
        # Support common containers for edited outputs as well
        videos: list[Path] = []
        for pattern in ("*.mkv", "*.mp4"):
            videos.extend(self.settings.edited_dir.glob(pattern))
        return videos

    def delete_edited(self, video: Path) -> bool:
        video = video.resolve()

        # 動画ファイルを削除
        if video.exists():
            video.unlink(missing_ok=True)

        # 関連ファイル（字幕、サムネイル、メタデータ）も削除
        subtitle = video.with_suffix(".srt")
        if subtitle.exists():
            subtitle.unlink(missing_ok=True)
        thumbnail = video.with_suffix(".png")
        if thumbnail.exists():
            thumbnail.unlink(missing_ok=True)
        metadata = video.with_suffix(".json")
        if metadata.exists():
            metadata.unlink(missing_ok=True)

        self._publisher.publish(
            EventTypes.ASSET_EDITED_DELETED, {"video": str(video)}
        )

        return (
            not video.exists()
            and not subtitle.exists()
            and not thumbnail.exists()
            and not metadata.exists()
        )

    def get_edited_subtitle(self, video: Path) -> str | None:
        """編集済み動画の字幕を取得する"""
        subtitle = video.with_suffix(".srt")
        if not subtitle.exists():
            return None
        try:
            return subtitle.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "編集済み動画の字幕読み込みに失敗しました",
                path=str(subtitle),
                error=str(exc),
            )
            return None

    def save_edited_subtitle(self, video: Path, content: str) -> bool:
        """編集済み動画の字幕を保存する"""
        subtitle = video.with_suffix(".srt")
        try:
            subtitle.parent.mkdir(parents=True, exist_ok=True)
            subtitle.write_text(content, encoding="utf-8")
            self.logger.info(
                "編集済み動画の字幕を保存しました", path=str(subtitle)
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "編集済み動画の字幕保存に失敗しました",
                path=str(subtitle),
                error=str(exc),
            )
            return False

    def get_edited_thumbnail(self, video: Path) -> bytes | None:
        """編集済み動画のサムネイルを取得する"""
        thumbnail = video.with_suffix(".png")
        if not thumbnail.exists():
            return None
        try:
            return thumbnail.read_bytes()
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "編集済み動画のサムネイル読み込みに失敗しました",
                path=str(thumbnail),
                error=str(exc),
            )
            return None

    def save_edited_thumbnail(self, video: Path, data: bytes) -> bool:
        """編集済み動画のサムネイルを保存する"""
        thumbnail = video.with_suffix(".png")
        try:
            thumbnail.parent.mkdir(parents=True, exist_ok=True)
            thumbnail.write_bytes(data)
            self.logger.info(
                "編集済み動画のサムネイルを保存しました", path=str(thumbnail)
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "編集済み動画のサムネイル保存に失敗しました",
                path=str(thumbnail),
                error=str(exc),
            )
            return False

    def get_edited_metadata(self, video: Path) -> dict[str, str] | None:
        """編集済み動画のメタデータを取得する"""
        metadata_path = video.with_suffix(".json")
        if not metadata_path.exists():
            return None
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            # 文字列型に変換
            return {
                str(k): str(v) if v is not None else ""
                for k, v in data.items()
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "編集済み動画のメタデータ読み込みに失敗しました",
                path=str(metadata_path),
                error=str(exc),
            )
            return None

    def save_edited_metadata_dict(
        self, video: Path, metadata: dict[str, str]
    ) -> bool:
        """編集済み動画のメタデータを保存する"""
        metadata_path = video.with_suffix(".json")
        try:
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.logger.info(
                "編集済み動画のメタデータを保存しました",
                path=str(metadata_path),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "編集済み動画のメタデータ保存に失敗しました",
                path=str(metadata_path),
                error=str(exc),
            )
            return False
