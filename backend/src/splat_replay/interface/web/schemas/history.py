"""対戦履歴スキーマ。

責務：
- /api/history/battle エンドポイントのレスポンス DTO を定義する。
- battle_history.json (バージョン 2) のフィールドに対応する。
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

__all__ = ["BattleHistoryItem", "BattleHistoryResponse"]


class BattleHistoryItem(BaseModel):
    """1試合分の対戦履歴アイテム。"""

    record_id: str
    source_video_id: str
    game_mode: str
    started_at: Optional[str] = None
    match: Optional[str] = None
    rule: Optional[str] = None
    stage: Optional[str] = None
    judgement: Optional[str] = None
    kill: Optional[int] = None
    death: Optional[int] = None
    special: Optional[int] = None
    assist: Optional[int] = None
    gold_medals: Optional[int] = None
    silver_medals: Optional[int] = None
    session_rate: Optional[str] = None


class BattleHistoryResponse(BaseModel):
    """対戦履歴レスポンス。"""

    records: List[BattleHistoryItem]
