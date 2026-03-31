"""Upload adapters."""

from __future__ import annotations

from splat_replay.infrastructure.adapters.upload.noop_upload_port import (
    NoOpUploadPort,
)
from splat_replay.infrastructure.adapters.upload.youtube_client import (
    YouTubeClient,
)

__all__ = [
    "NoOpUploadPort",
    "YouTubeClient",
]
