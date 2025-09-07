"""録画時に保存するメタデータクラス。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from splat_replay.shared.logger import get_logger

from .game_mode import GameMode
from .judgement import Judgement
from .rate import RateBase
from .result import BattleResult, Result, SalmonResult


@dataclass
class RecordingMetadata:
    """録画時点での簡易メタデータ。"""

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

    def to_dict(self) -> Dict[str, str | None]:
        """辞書へ変換する。"""
        dict = {
            "game_mode": self.game_mode.value,
            "started_at": self.started_at.isoformat()
            if self.started_at
            else None,
            "rate": str(self.rate) if self.rate else None,
            "judgement": self.judgement.value if self.judgement else None,
        }
        if self.result:
            dict.update(self.result.to_dict())
        return dict

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "RecordingMetadata":
        """辞書からインスタンスを生成する。"""
        logger = get_logger()

        game_mode_str = data.get("game_mode")
        if game_mode_str is None:
            raise ValueError("game_mode is required")
        try:
            game_mode = GameMode(game_mode_str)
        except Exception as e:
            logger.error(
                f"ゲームモードの変換に失敗しました({game_mode_str}): {e}"
            )
            raise ValueError("game_mode is invalid")

        started_at_str = data.get("started_at")
        try:
            started_at = (
                datetime.fromisoformat(started_at_str)
                if started_at_str
                else None
            )
        except Exception as e:
            logger.error(
                f"開始時刻の変換に失敗しました({started_at_str}): {e}"
            )
            started_at = None

        rate_str = data.get("rate")
        try:
            rate = RateBase.create(rate_str) if rate_str else None
        except Exception as e:
            logger.error(f"レートの変換に失敗しました({rate_str}): {e}")
            rate = None

        judgement_str = data.get("judgement")
        try:
            judgement = Judgement(judgement_str) if judgement_str else None
        except Exception as e:
            logger.error(
                f"ジャッジメントの変換に失敗しました({judgement_str}): {e}"
            )
            judgement = None

        try:
            if game_mode == GameMode.BATTLE:
                result = BattleResult.from_dict(data)
            elif game_mode == GameMode.SALMON:
                result = SalmonResult.from_dict(data)
            else:
                result = None
        except Exception as e:
            logger.error(f"結果の変換に失敗しました{data}: {e}")
            result = None

        return cls(
            game_mode=game_mode,
            started_at=started_at,
            rate=rate,
            judgement=judgement,
            result=result,
        )
