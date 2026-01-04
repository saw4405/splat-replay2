"""Metadata-related schemas for Web API.

メタデータ機能に関するリクエスト/レスポンス スキーマを定義する。
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

__all__ = [
    "MetadataUpdateRequest",
    "SubtitleBlock",
    "SubtitleData",
]


class MetadataUpdateRequest(BaseModel):
    """録画済みビデオのメタデータ更新リクエスト"""

    match: Optional[str] = None
    rule: Optional[str] = None
    stage: Optional[str] = None
    rate: Optional[str] = None
    judgement: Optional[str] = None
    kill: Optional[int] = None
    death: Optional[int] = None
    special: Optional[int] = None


class SubtitleBlock(BaseModel):
    """字幕ブロック"""

    index: int
    start_time: float  # 秒単位
    end_time: float  # 秒単位
    text: str


class SubtitleData(BaseModel):
    """字幕データ"""

    blocks: List[SubtitleBlock]
    video_duration: Optional[float] = None
