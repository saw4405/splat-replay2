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


def _has_required_fields(
    data: Mapping[str, object], required_fields: tuple[str, ...]
) -> bool:
    for field in required_fields:
        if field not in data:
            return False
        value = data.get(field)
        if value is None:
            return False
        if isinstance(value, str) and not value:
            return False
    return True


BATTLE_RESULT_REQUIRED_FIELDS: tuple[str, ...] = (
    "match",
    "rule",
    "stage",
    "kill",
    "death",
    "special",
)

SALMON_RESULT_REQUIRED_FIELDS: tuple[str, ...] = (
    "hazard",
    "stage",
    "golden_egg",
    "power_egg",
    "rescue",
    "rescued",
)


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

    def update_from_dict(self, data: Mapping[str, object]) -> None:
        """手動編集されたメタデータで部分的に更新する。"""
        logger = get_logger()

        # game_mode
        game_mode_raw = data.get("game_mode")
        if isinstance(game_mode_raw, str) and game_mode_raw:
            try:
                self.game_mode = GameMode(game_mode_raw)
            except Exception as e:
                logger.warning(
                    f"ゲームモードの解釈に失敗しました({game_mode_raw}): {e}"
                )

        # started_at
        started_at_raw = data.get("started_at")
        if isinstance(started_at_raw, str) and started_at_raw:
            try:
                self.started_at = datetime.fromisoformat(started_at_raw)
            except Exception as e:
                logger.warning(
                    f"開始時刻の解釈に失敗しました({started_at_raw}): {e}"
                )

        # rate
        rate_raw = data.get("rate")
        if isinstance(rate_raw, str) and rate_raw:
            try:
                self.rate = RateBase.create(rate_raw)
            except Exception as e:
                logger.warning(f"レートの解釈に失敗しました({rate_raw}): {e}")

        # judgement
        judgement_raw = data.get("judgement")
        if isinstance(judgement_raw, str) and judgement_raw:
            try:
                self.judgement = Judgement(judgement_raw)
            except Exception as e:
                logger.warning(
                    f"ジャッジ結果の解釈に失敗しました({judgement_raw}): {e}"
                )

        # result (BattleResult or SalmonResult)
        if self.result is not None:
            # 既存の result を更新
            if isinstance(self.result, BattleResult):
                self.result.update_from_dict(data)
            elif isinstance(self.result, SalmonResult):
                self.result.update_from_dict(data)

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

        result: Result | None = None
        if game_mode == GameMode.BATTLE:
            if _has_required_fields(data, BATTLE_RESULT_REQUIRED_FIELDS):
                try:
                    result = BattleResult.from_dict(data)
                except Exception as e:
                    logger.error(f"リザルト�E解釈に失敗しました{data}: {e}")
                    result = None
        elif game_mode == GameMode.SALMON:
            if _has_required_fields(data, SALMON_RESULT_REQUIRED_FIELDS):
                try:
                    result = SalmonResult.from_dict(data)
                except Exception as e:
                    logger.error(f"リザルト�E解釈に失敗しました{data}: {e}")
                    result = None

        return cls(
            game_mode=game_mode,
            started_at=started_at,
            rate=rate,
            judgement=judgement,
            result=result,
        )
