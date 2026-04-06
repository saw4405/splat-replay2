"""対戦履歴ルーター。

責務：
- 対戦履歴の一覧取得エンドポイントを提供する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from splat_replay.application.metadata.codec import serialize_metadata_value
from splat_replay.domain.models import BattleResult
from splat_replay.interface.web.schemas.history import (
    BattleHistoryItem,
    BattleHistoryResponse,
)

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


def create_history_router(server: WebAPIServer) -> APIRouter:
    """対戦履歴ルーターを作成する。"""

    router = APIRouter(prefix="/api", tags=["history"])

    @router.get("/history/battle", response_model=BattleHistoryResponse)
    def get_battle_history() -> BattleHistoryResponse:
        """対戦履歴の一覧を取得する。"""
        entries = server.list_battle_history_uc.execute()
        items = []
        for entry in entries:
            m = entry.metadata
            result = m.result if isinstance(m.result, BattleResult) else None
            items.append(
                BattleHistoryItem(
                    record_id=entry.source_video_id,
                    source_video_id=entry.source_video_id,
                    game_mode=m.game_mode.name
                    if m.game_mode is not None
                    else None,
                    started_at=(
                        m.started_at.isoformat()
                        if m.started_at is not None
                        else None
                    ),
                    match=(
                        result.match.name
                        if result is not None and result.match is not None
                        else None
                    ),
                    rule=(
                        result.rule.name
                        if result is not None and result.rule is not None
                        else None
                    ),
                    stage=(
                        result.stage.name
                        if result is not None and result.stage is not None
                        else None
                    ),
                    judgement=(
                        m.judgement.name if m.judgement is not None else None
                    ),
                    kill=result.kill if result is not None else None,
                    death=result.death if result is not None else None,
                    special=result.special if result is not None else None,
                    gold_medals=result.gold_medals
                    if result is not None
                    else None,
                    silver_medals=result.silver_medals
                    if result is not None
                    else None,
                    session_rate=(
                        str(serialize_metadata_value(m.rate))
                        if m.rate is not None
                        else None
                    ),
                )
            )
        return BattleHistoryResponse(records=items)

    return router
