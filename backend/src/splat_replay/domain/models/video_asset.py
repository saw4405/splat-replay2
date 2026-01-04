"""Video asset metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .recording_metadata import RecordingMetadata


@dataclass(frozen=True)
class VideoAsset:
    """Represents a recorded video and aligned sidecar files.

    This is an immutable Value Object representing a video recording
    and its associated metadata files (subtitle, thumbnail, metadata JSON).
    """

    video: Path
    subtitle: Path | None = None
    thumbnail: Path | None = None
    metadata: RecordingMetadata | None = None
