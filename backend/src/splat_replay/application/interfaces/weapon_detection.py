"""ブキ判別ポート定義。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from splat_replay.domain.models import Frame

__all__ = [
    "WeaponRecognitionPort",
    "WeaponCandidateScore",
    "WeaponSlotResult",
    "WeaponRecognitionResult",
]


@dataclass(frozen=True)
class WeaponCandidateScore:
    """候補ブキとスコア。"""

    weapon: str
    score: float


@dataclass(frozen=True)
class WeaponSlotResult:
    """1スロット分の判別結果。"""

    slot: str
    predicted_weapon: str
    is_unmatched: bool
    top_candidates: tuple[WeaponCandidateScore, ...]

    @property
    def best_score(self) -> float:
        """top1 スコアを返す。候補なしは -1.0。"""
        if not self.top_candidates:
            return -1.0
        return self.top_candidates[0].score


@dataclass(frozen=True)
class WeaponRecognitionResult:
    """8スロット分の判別結果。"""

    allies: tuple[str, str, str, str]
    enemies: tuple[str, str, str, str]
    slot_results: tuple[WeaponSlotResult, ...]
    unmatched_output_dir: str | None = None


class WeaponRecognitionPort(Protocol):
    """ブキ表示検出とブキ判別を提供するポート。"""

    async def detect_weapon_display(self, frame: Frame) -> bool:
        """ブキ表示画面かどうかを判定する。"""
        ...

    async def recognize_weapons(
        self,
        frame: Frame,
        save_unmatched_report: bool = True,
    ) -> WeaponRecognitionResult:
        """味方4+敵4のブキを判別する。"""
        ...
