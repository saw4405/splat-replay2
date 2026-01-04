"""Video processing ports (editing, repository)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from splat_replay.application.interfaces.data import FileStats
from splat_replay.domain.models import Frame, RecordingMetadata, VideoAsset


class VideoEditorPort(Protocol):
    """動画編集処理を提供するポート。"""

    async def merge(self, clips: list[Path], output: Path) -> Path:
        """Merge multiple video clips into one."""
        ...

    async def embed_metadata(
        self, path: Path, metadata: dict[str, str]
    ) -> None:
        """Embed metadata into video file."""
        ...

    async def get_metadata(self, path: Path) -> dict[str, str]:
        """Get metadata from video file."""
        ...

    async def embed_subtitle(self, path: Path, srt: str) -> None:
        """Embed subtitle into video file."""
        ...

    async def get_subtitle(self, path: Path) -> Optional[str]:
        """Get subtitle from video file."""
        ...

    async def embed_thumbnail(self, path: Path, thumbnail: bytes) -> None:
        """Embed thumbnail into video file."""
        ...

    async def get_thumbnail(self, path: Path) -> Optional[bytes]:
        """Get thumbnail from video file."""
        ...

    async def change_volume(self, path: Path, multiplier: float) -> None:
        """Change audio volume by multiplier."""
        ...

    async def get_video_length(self, path: Path) -> Optional[float]:
        """Get video length in seconds."""
        ...

    async def add_audio_track(
        self,
        path: Path,
        audio: Path,
        *,
        stream_title: Optional[str] = None,
    ) -> None:
        """Add audio track to video."""
        ...

    async def list_video_devices(self) -> list[str]:
        """List available video capture devices."""
        ...


class VideoAssetRepositoryPort(Protocol):
    """動画ファイルを保存・管理するポート."""

    def get_recorded_dir(self) -> Path:
        """Get recorded videos directory."""
        ...

    def get_edited_dir(self) -> Path:
        """Get edited videos directory."""
        ...

    def save_recording(
        self,
        video: Path,
        srt: Path | None,
        screenshot: Frame | None,
        metadata: RecordingMetadata,
    ) -> VideoAsset:
        """Save recorded video with metadata."""
        ...

    def get_asset(self, video: Path) -> VideoAsset | None:
        """Get video asset by path."""
        ...

    def get_file_stats(self, video: Path) -> FileStats | None:
        """Get file stats for a video path."""
        ...

    def has_subtitle(self, video: Path) -> bool:
        """Check if subtitle sidecar exists."""
        ...

    def has_thumbnail(self, video: Path) -> bool:
        """Check if thumbnail sidecar exists."""
        ...

    def save_edited_metadata(
        self, video: Path, metadata: RecordingMetadata
    ) -> None:
        """Save edited video metadata."""
        ...

    def list_recordings(self) -> list[VideoAsset]:
        """List all recorded videos."""
        ...

    def delete_recording(self, video: Path) -> bool:
        """Delete recorded video."""
        ...

    def get_subtitle(self, video: Path) -> Optional[str]:
        """Get subtitle for recorded video."""
        ...

    def save_subtitle(self, video: Path, content: str) -> bool:
        """Save subtitle for recorded video."""
        ...

    def save_edited(self, video: Path) -> Path:
        """Save edited video."""
        ...

    def list_edited(self) -> list[Path]:
        """List all edited videos."""
        ...

    def delete_edited(self, video: Path) -> bool:
        """Delete edited video."""
        ...

    def get_edited_subtitle(self, video: Path) -> Optional[str]:
        """Get subtitle for edited video."""
        ...

    def save_edited_subtitle(self, video: Path, content: str) -> bool:
        """Save subtitle for edited video."""
        ...

    def get_edited_thumbnail(self, video: Path) -> Optional[bytes]:
        """Get thumbnail for edited video."""
        ...

    def save_edited_thumbnail(self, video: Path, data: bytes) -> bool:
        """Save thumbnail for edited video."""
        ...

    def get_edited_metadata(self, video: Path) -> Optional[dict[str, str]]:
        """Get metadata for edited video."""
        ...

    def save_edited_metadata_dict(
        self, video: Path, metadata: dict[str, str]
    ) -> bool:
        """Save metadata dict for edited video."""
        ...
