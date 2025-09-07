"""動画ファイルを保存・管理するリポジトリ実装."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    EventPublisher,
    VideoAssetRepository,
)
from splat_replay.domain.models import (
    BattleResult,
    RecordingMetadata,
    VideoAsset,
)
from splat_replay.shared.config import VideoStorageSettings
from splat_replay.shared.event_types import EventTypes


class FileVideoAssetRepository(VideoAssetRepository):
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
        if self._publisher:
            try:
                from splat_replay.shared.event_types import EventTypes

                self._publisher.publish(
                    EventTypes.ASSET_RECORDED_METADATA_UPDATED,
                    {"video": str(video)},
                )
            except Exception:
                pass

    def list_recordings(self) -> list[VideoAsset]:
        assets: list[VideoAsset] = []
        # Support common containers produced by OBS (mkv/mp4)
        for pattern in ("*.mkv", "*.mp4"):
            for video in self.settings.recorded_dir.glob(pattern):
                assets.append(VideoAsset.load(video))
        return assets

    def delete_recording(self, video: Path) -> None:
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
        if self._publisher:
            try:
                from splat_replay.shared.event_types import EventTypes

                self._publisher.publish(
                    EventTypes.ASSET_RECORDED_DELETED,
                    {"video": str(video)},
                )
            except Exception:
                pass

    def save_edited(self, video: Path) -> Path:
        dest = self.settings.edited_dir
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / video.name
        try:
            shutil.move(str(video), target)
        except Exception:
            target = video
        self.logger.info("編集後ファイル保存", path=str(target))
        if self._publisher:
            try:
                from splat_replay.shared.event_types import EventTypes

                self._publisher.publish(
                    EventTypes.ASSET_EDITED_SAVED, {"video": str(target)}
                )
            except Exception:
                pass
        return target

    def list_edited(self) -> list[Path]:
        # Support common containers for edited outputs as well
        videos: list[Path] = []
        for pattern in ("*.mkv", "*.mp4"):
            videos.extend(self.settings.edited_dir.glob(pattern))
        return videos

    def delete_edited(self, video: Path) -> None:
        video = video.resolve()
        if video.exists():
            video.unlink(missing_ok=True)
        if self._publisher:
            try:
                from splat_replay.shared.event_types import EventTypes

                self._publisher.publish(
                    EventTypes.ASSET_EDITED_DELETED, {"video": str(video)}
                )
            except Exception:
                pass
