from typing import List, Optional, Literal

from pydantic import BaseModel


class UploadSettings(BaseModel):
    """アップロード関連の設定。"""

    privacy_status: Literal["public", "unlisted", "private"] = "private"
    tags: Optional[List[str]] = None
    playlist_id: Optional[str] = None
    caption_name: str = "ひとりごと"

    class Config:
        pass
