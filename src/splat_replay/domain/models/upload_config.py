from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class YouTubeUploadConfig(BaseModel):
    """YouTube へのアップロード設定を表す簡易モデル."""

    title: str = ""
    description: str = ""
    tags: List[str] | None = None
    playlist_id: Optional[str] = None
