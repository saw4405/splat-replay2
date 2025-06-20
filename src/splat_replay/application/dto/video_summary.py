"""アップロード結果などをまとめた DTO。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VideoSummary:
    """動画の概要情報。"""

    video_id: str
    url: str
