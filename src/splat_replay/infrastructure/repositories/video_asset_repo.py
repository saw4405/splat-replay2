"""動画ファイルを保存・管理するリポジトリ実装."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from splat_replay.application.interfaces import VideoAssetRepository
from splat_replay.domain.models import RecordingMetadata, VideoAsset
from splat_replay.shared.config import VideoStorageSettings
from splat_replay.shared.logger import get_logger


class FileVideoAssetRepository(VideoAssetRepository):
    """ファイルシステム上で VideoAsset を管理する実装."""

    def __init__(self, settings: VideoStorageSettings) -> None:
        self.settings = settings
        self.logger = get_logger()

    def _name_from_metadata(
        self, meta: RecordingMetadata | None, default: str
    ) -> str:
        parts: list[str] = []
        if meta is None:
            return default
        if meta.started_at:
            parts.append(meta.started_at.strftime("%Y%m%d_%H%M%S"))
        if meta.rate:
            parts.append(meta.rate.short_str())
        if meta.judgement:
            parts.append(meta.judgement)
        if (
            meta.kill is not None
            and meta.death is not None
            and meta.special is not None
        ):
            parts.append(f"{meta.kill}k{meta.death}d{meta.special}s")
        return "_".join(parts) if parts else default

    def save_recording(
        self,
        video: Path,
        subtitle: str,
        screenshot: np.ndarray,
        metadata: RecordingMetadata,
    ) -> VideoAsset:
        dest = self.settings.recorded_dir
        dest.mkdir(parents=True, exist_ok=True)
        name_root = self._name_from_metadata(metadata, video.stem)
        target = dest / f"{name_root}{video.suffix}"
        try:
            shutil.move(str(video), target)
        except Exception:
            target = video
        cv2.imwrite(str(dest / f"{name_root}.png"), screenshot)
        (dest / f"{name_root}.srt").write_text(subtitle)
        (dest / f"{name_root}.json").write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False)
        )
        self.logger.info("録画ファイル保存", path=str(target))
        return VideoAsset(
            video=target,
            subtitle=dest / f"{name_root}.srt",
            thumbnail=dest / f"{name_root}.png",
            metadata=metadata,
        )

    def list_recordings(self) -> list[VideoAsset]:
        assets: list[VideoAsset] = []
        for video in self.settings.recorded_dir.glob("*.mp4"):
            assets.append(VideoAsset.load(video))
        return assets

    def save_edited(self, video: Path) -> Path:
        dest = self.settings.edited_dir
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / video.name
        try:
            shutil.move(str(video), target)
        except Exception:
            target = video
        self.logger.info("編集後ファイル保存", path=str(target))
        return target

    def list_edited(self) -> list[Path]:
        return list(self.settings.edited_dir.glob("*.mp4"))
