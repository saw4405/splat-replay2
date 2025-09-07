"""動画ファイルと付随データをまとめて扱うクラス。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .recording_metadata import RecordingMetadata


@dataclass
class VideoAsset:
    """動画・字幕・サムネイル・メタデータをまとめて保持する。"""

    video: Path
    subtitle: Path | None = None
    thumbnail: Path | None = None
    metadata: RecordingMetadata | None = None

    @classmethod
    def load(cls, video: Path) -> "VideoAsset":
        """動画パスから関連ファイルを読み込む。"""
        subtitle = video.with_suffix(".srt")
        if not subtitle.exists():
            subtitle = None
        thumbnail = video.with_suffix(".png")
        if not thumbnail.exists():
            thumbnail = None
        meta_file = video.with_suffix(".json")
        metadata = None
        if meta_file.exists():
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            metadata = RecordingMetadata.from_dict(data)
        return cls(
            video=video,
            subtitle=subtitle,
            thumbnail=thumbnail,
            metadata=metadata,
        )
