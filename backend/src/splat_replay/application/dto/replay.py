"""E2E リプレイ入力由来の bootstrap DTO。"""

from __future__ import annotations

from dataclasses import dataclass

from splat_replay.domain.models import GameMode


@dataclass(frozen=True)
class ReplayBootstrapDTO:
    """自動録画開始前に適用する録画コンテキスト初期値。"""

    phase: str
    game_mode: GameMode | None = None
