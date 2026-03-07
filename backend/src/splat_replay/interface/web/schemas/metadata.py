"""Metadata-related schemas for Web API.

メタデータ機能に関するリクエスト/レスポンス スキーマを定義する。
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, root_validator

__all__ = [
    "MetadataOptionItem",
    "MetadataOptionsResponse",
    "MetadataUpdateRequest",
    "SubtitleBlock",
    "SubtitleData",
]


class MetadataOptionItem(BaseModel):
    """メタデータ選択肢アイテム"""

    key: str
    label: str


class MetadataOptionsResponse(BaseModel):
    """メタデータ選択肢レスポンス"""

    game_modes: List[MetadataOptionItem]
    matches: List[MetadataOptionItem]
    rules: List[MetadataOptionItem]
    stages: List[MetadataOptionItem]
    judgements: List[MetadataOptionItem]


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
    gold_medals: Optional[int] = Field(None, ge=0, le=3)
    silver_medals: Optional[int] = Field(None, ge=0, le=3)
    allies: Optional[List[str]] = None
    enemies: Optional[List[str]] = None

    @root_validator
    def validate_medal_total(
        cls, values: dict[str, object]
    ) -> dict[str, object]:
        gold_medals = values.get("gold_medals")
        silver_medals = values.get("silver_medals")
        if (
            isinstance(gold_medals, int)
            and isinstance(silver_medals, int)
            and gold_medals + silver_medals > 3
        ):
            raise ValueError(
                "gold_medals と silver_medals の合計は 3 以下で指定してください"
            )
        return values


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
