"""Recording metadata aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from splat_replay.shared.logger import get_logger

from .game_mode import GameMode
from .judgement import Judgement
from .rate import RateBase
from .result import BattleResult, Result, SalmonResult


@dataclass
class RecordingMetadata:
    """State captured during an automated recording session."""

    game_mode: GameMode = GameMode.BATTLE
    started_at: datetime | None = None
    rate: RateBase | None = None
    judgement: Judgement | None = None
    result: Result | None = None

    def reset(self) -> None:
        self.started_at = None
        self.rate = None
        self.judgement = None
        self.result = None

    def to_dict(self) -> dict[str, str | int | None]:
        """Serialize into a JSON-friendly dictionary."""
        payload: dict[str, str | int | None] = {
            "game_mode": self.game_mode.value,
            "started_at": self.started_at.isoformat()
            if self.started_at
            else None,
            "rate": str(self.rate) if self.rate else None,
            "judgement": self.judgement.value if self.judgement else None,
        }
        if self.result:
            payload.update(self.result.to_dict())
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "RecordingMetadata":
        """Rehydrate metadata from persisted data."""
        logger = get_logger()

        game_mode_raw = data.get("game_mode")
        if not isinstance(game_mode_raw, str):
            raise ValueError("game_mode is required")
        try:
            game_mode = GameMode(game_mode_raw)
        except Exception as e:
            logger.error(
                f"ゲームモードの解釈に失敗しました({game_mode_raw}): {e}"
            )
            raise ValueError("game_mode is invalid")

        started_at_raw = data.get("started_at")
        started_at: datetime | None
        try:
            if isinstance(started_at_raw, str) and started_at_raw:
                started_at = datetime.fromisoformat(started_at_raw)
            else:
                started_at = None
        except Exception as e:
            logger.error(
                f"開始時刻の解釈に失敗しました({started_at_raw}): {e}"
            )
            started_at = None

        rate_raw = data.get("rate")
        rate: RateBase | None
        try:
            if isinstance(rate_raw, str) and rate_raw:
                rate = RateBase.create(rate_raw)
            else:
                rate = None
        except Exception as e:
            logger.error(f"レートの解釈に失敗しました({rate_raw}): {e}")
            rate = None

        judgement_raw = data.get("judgement")
        judgement: Judgement | None
        try:
            if isinstance(judgement_raw, str) and judgement_raw:
                judgement = Judgement(judgement_raw)
            else:
                judgement = None
        except Exception as e:
            logger.error(
                f"ジャッジ結果の解釈に失敗しました({judgement_raw}): {e}"
            )
            judgement = None

        result: Result | None
        try:
            if game_mode == GameMode.BATTLE:
                result = BattleResult.from_dict(data)
            elif game_mode == GameMode.SALMON:
                result = SalmonResult.from_dict(data)
            else:
                result = None
        except Exception as e:
            logger.error(f"リザルトの解釈に失敗しました{data}: {e}")
            result = None

        return cls(
            game_mode=game_mode,
            started_at=started_at,
            rate=rate,
            judgement=judgement,
            result=result,
        )
