"""ブキ判別ポート定義。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from splat_replay.domain.models import Frame

__all__ = [
    "WeaponRecognitionPort",
    "WeaponCandidateScore",
    "WeaponDisplayDetectionResult",
    "WeaponSlotResult",
    "WeaponRecognitionResult",
]


@dataclass(frozen=True)
class WeaponCandidateScore:
    """候補ブキとスコア。"""

    weapon: str
    score: float
    threshold: float


@dataclass(frozen=True)
class WeaponDisplayDetectionResult:
    """ブキ表示判定の詳細結果。"""

    is_visible: bool
    should_recognize: bool
    score: float = 0.0
    ally_reliable_slot_count: int = 0
    enemy_reliable_slot_count: int = 0
    outline_matched_slots: int = 0
    outline_matched_ally_slots: int = 0
    outline_matched_enemy_slots: int = 0
    outline_team_slots_reliable: bool = False
    display_weapon_region_ratio: float | None = None
    display_weapon_region_ratio_passed: bool | None = None
    matched_slot_team_edge_ratio: float | None = None
    matched_slot_team_edge_ratio_passed: bool | None = None
    matched_slot_weapon_region_gray_std: float | None = None
    matched_slot_weapon_region_gray_std_passed: bool | None = None
    fallback_used: bool = False
    reason: str = ""


@dataclass(frozen=True)
class WeaponSlotResult:
    """1スロット分の判別結果。"""

    slot: str
    predicted_weapon: str
    is_unmatched: bool
    top_candidates: tuple[WeaponCandidateScore, ...]
    detected_score: float | None = None

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
    predict_weapons_output_dir: str | None = None


class WeaponRecognitionPort(Protocol):
    """ブキ表示検出とブキ判別を提供するポート。"""

    def request_cancel(self) -> None:
        """進行中の判別処理を中断要求する。"""
        ...

    async def detect_weapon_display(self, frame: Frame) -> bool:
        """ブキ表示画面かどうかを判定する。"""
        ...

    async def detect_weapon_display_details(
        self, frame: Frame
    ) -> WeaponDisplayDetectionResult:
        """ブキ表示判定の詳細結果を返す。"""
        ...

    async def recognize_weapons(
        self,
        frame: Frame,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        """味方4+敵4のブキを判別する（ブキ表示画面入力を前提とする）。

        Args:
            frame: 入力フレーム
            save_predict_weapons_output: predict_weapons 出力を保存するか
            target_slots: 判別対象のスロットのセット。Noneの場合は全スロット。
            previous_results: 既存の判定結果。target_slotsに含まれないスロットはこの結果を使用。
            battle_dir_name: predict_weapons 保存時のバトルフォルダ名。
        """
        ...

    async def save_predict_weapons_output(
        self,
        frame: Frame,
        slot_results: tuple[WeaponSlotResult, ...],
        battle_dir_name: str | None = None,
    ) -> str | None:
        """判別済みの結果から predict_weapons 出力だけを保存する。

        ブキ判別は再実行しない。
        """
        ...
