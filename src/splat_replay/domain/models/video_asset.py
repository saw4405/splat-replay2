"""Video asset metadata helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .recording_metadata import RecordingMetadata


@dataclass
class VideoAsset:
    """Represents a recorded video and aligned sidecar files."""

    video: Path
    subtitle: Path | None = None
    thumbnail: Path | None = None
    metadata: RecordingMetadata | None = None

    @classmethod
    def load(cls, video: Path) -> "VideoAsset":
        """Construct an asset from disk if sidecar files exist."""
        subtitle_candidate = video.with_suffix(".srt")
        subtitle: Path | None = (
            subtitle_candidate if subtitle_candidate.exists() else None
        )
        thumbnail_candidate = video.with_suffix(".png")
        thumbnail: Path | None = (
            thumbnail_candidate if thumbnail_candidate.exists() else None
        )
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
