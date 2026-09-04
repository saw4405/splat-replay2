"""Upload-related ports (YouTube, authentication)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Protocol

from splat_replay.application.interfaces.data import Caption, PrivacyStatus


class UploadPort(Protocol):
    """動画アップロード処理を提供するポート。"""

    def upload(
        self,
        path: Path,
        title: str,
        description: str,
        tags: List[str] = [],
        privacy_status: PrivacyStatus = "private",
        thumb: Optional[Path] = None,
        caption: Optional[Caption] = None,
        playlist_id: str = "",
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Upload video to platform."""
        ...


class AuthenticatedClientPort(Protocol):
    """認証済みのクライアントを提供するポート。"""

    def authenticate(self) -> None:
        """Authenticate client."""
        ...
