"""自動編集ユースケース。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from splat_replay.application.interfaces import (
    VideoEditorPort,
    VideoAssetRepository,
)
from splat_replay.domain.models import VideoAsset
from splat_replay.infrastructure.adapters.ffmpeg_processor import (
    FFmpegProcessor,
)
from splat_replay.shared.logger import get_logger


class AutoEditUseCase:
    """録画済み動画を検索して編集を行う。"""

    def __init__(
        self,
        editor: VideoEditorPort,
        ffmpeg: FFmpegProcessor,
        repo: VideoAssetRepository,
    ) -> None:
        self.editor = editor
        self.ffmpeg = ffmpeg
        self.repo = repo
        self.logger = get_logger()

    def _schedule_key(self, dt: datetime | None) -> str:
        if dt is None:
            return "unknown"
        start = dt.replace(minute=0, second=0, microsecond=0)
        start -= timedelta(hours=start.hour % 2)
        return start.strftime("%Y%m%d_%H")

    def _collect_assets(self) -> list[VideoAsset]:
        return self.repo.list_recordings()

    def execute(self) -> list[Path]:
        """録画フォルダ内の動画を編集して返す。"""
        assets = self._collect_assets()
        groups: dict[tuple[str, str], list[VideoAsset]] = defaultdict(list)
        for asset in assets:
            meta = asset.metadata
            key = (
                self._schedule_key(meta.started_at) if meta else "unknown",
                meta.match.name if meta and meta.match else "unknown",
            )
            groups[key].append(asset)
        edited: list[Path] = []
        for key, clips in groups.items():
            if not clips:
                continue
            target_asset = clips[0]
            if len(clips) > 1:
                merged_path = self.ffmpeg.merge([c.video for c in clips])
                target_asset = VideoAsset.load(merged_path)
                target_asset.metadata = clips[0].metadata
                self.logger.info(
                    "結合完了",
                    group=str(key),
                    clips=[c.video.name for c in clips],
                )
            out = self.editor.process(target_asset.video)
            if target_asset.subtitle:
                self.ffmpeg.embed_subtitle(out, target_asset.subtitle)
            target = self.repo.save_edited(Path(out))
            edited.append(target)
        return edited
