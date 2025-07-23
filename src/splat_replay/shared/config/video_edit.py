from typing import Optional

from pydantic import BaseModel


class VideoEditSettings(BaseModel):
    """動画編集処理の設定。"""

    volume_multiplier: float = 1.0
    title_template: Optional[str] = None
    description_template: Optional[str] = None
    chapter_template: Optional[str] = None

    class Config:
        pass
