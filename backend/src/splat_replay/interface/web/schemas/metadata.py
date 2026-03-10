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
    "RecordingMetadataResponse",
    "RecordingMetadataUpdateRequest",
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


class _BattleMetadataUpdateFields(BaseModel):
    """バトル系メタデータ更新フィールド。"""

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


class MetadataUpdateRequest(_BattleMetadataUpdateFields):
    """録画済みビデオのメタデータ更新リクエスト"""

    started_at: Optional[str] = None


class RecordingMetadataUpdateRequest(_BattleMetadataUpdateFields):
    """録画中メタデータ更新リクエスト。"""

    game_mode: Optional[str] = None
    started_at: Optional[str] = None
    hazard: Optional[int] = None
    golden_egg: Optional[int] = None
    power_egg: Optional[int] = None
    rescue: Optional[int] = None
    rescued: Optional[int] = None


class RecordingMetadataResponse(BaseModel):
    """録画中メタデータレスポンス。"""

    game_mode: str | None = Field(None, description="ゲームモード")
    stage: str | None = Field(None, description="ステージ")
    started_at: str | None = Field(None, description="開始時刻")
    match: str | None = Field(None, description="マッチ")
    rule: str | None = Field(None, description="ルール")
    rate: str | None = Field(None, description="レート")
    judgement: str | None = Field(None, description="判定")
    kill: int | None = Field(None, description="キル数")
    death: int | None = Field(None, description="デス数")
    special: int | None = Field(None, description="スペシャル数")
    gold_medals: int | None = Field(None, description="金表彰数")
    silver_medals: int | None = Field(None, description="銀表彰数")
    allies: list[str] | None = Field(None, description="味方4人のブキ")
    enemies: list[str] | None = Field(None, description="敵4人のブキ")
    hazard: int | None = Field(None, description="危険度")
    golden_egg: int | None = Field(None, description="金イクラ数")
    power_egg: int | None = Field(None, description="イクラ数")
    rescue: int | None = Field(None, description="救助数")
    rescued: int | None = Field(None, description="救助された数")


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
