"""動画ファイルを保存・管理するリポジトリ実装."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from structlog.stdlib import BoundLogger

from splat_replay.shared.config import VideoStorageSettings
from splat_replay.domain.models import (
    RecordingMetadata,
    VideoAsset,
    BattleResult,
)
from splat_replay.application.interfaces import VideoAssetRepository


class FileVideoAssetRepository(VideoAssetRepository):
    """ファイルシステム上で VideoAsset を管理する実装."""

    def __init__(
        self,
        settings: VideoStorageSettings,
        logger: BoundLogger,
    ) -> None:
        self.settings = settings
        self.logger = logger

    def save_recording(
        self,
        video: Path,
        subtitle: str,
        screenshot: np.ndarray | None,
        metadata: RecordingMetadata,
    ) -> VideoAsset:
        dest = self.settings.recorded_dir
        dest.mkdir(parents=True, exist_ok=True)
        if isinstance(metadata.result, BattleResult):
            name_root = "_".join(
                [
                    metadata.started_at.strftime("%Y%m%d_%H%M%S"),
                    metadata.result.match.value,
                    metadata.result.rule.value,
                    metadata.judgement or "",
                    metadata.result.stage.value,
                ]
            )
        else:
            name_root = metadata.started_at.strftime("%Y%m%d_%H%M%S")
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
        (dest / f"{name_root}.srt").write_text(subtitle, encoding="utf-8")
        (dest / f"{name_root}.json").write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False),
            encoding="utf-8",
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
        for video in self.settings.recorded_dir.glob("*.mkv"):
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
        return list(self.settings.edited_dir.glob("*.mkv"))

    def delete_edited(self, video: Path) -> None:
        video = video.resolve()
        if video.exists():
            video.unlink(missing_ok=True)
