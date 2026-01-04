"""Editing-related schemas for Web API.

編集機能に関するリクエスト/レスポンス スキーマを定義する。
"""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel

__all__ = [
    "RecordedVideoItem",
    "EditedVideoItem",
]


class RecordedVideoItem(BaseModel):
    """録画済みビデオアイテム"""

    id: str
    path: str
    filename: str
    started_at: Optional[str] = None
    game_mode: Optional[str] = None
    match: Optional[str] = None
    rule: Optional[str] = None
    stage: Optional[str] = None
    rate: Optional[str] = None
    judgement: Optional[str] = None
    kill: Optional[int] = None
    death: Optional[int] = None
    special: Optional[int] = None
    hazard: Optional[int] = None
    golden_egg: Optional[int] = None
    power_egg: Optional[int] = None
    rescue: Optional[int] = None
    rescued: Optional[int] = None
    has_subtitle: bool
    has_thumbnail: bool
    duration_seconds: Optional[float] = None
    size_bytes: Optional[int] = None


class EditedVideoItem(BaseModel):
    """編集済みビデオアイテム"""

    id: str
    path: str
    filename: str
    duration_seconds: Optional[float] = None
    has_subtitle: bool
    has_thumbnail: bool
    metadata: Optional[Dict[str, Optional[str]]] = None
    updated_at: Optional[str] = None
    size_bytes: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
