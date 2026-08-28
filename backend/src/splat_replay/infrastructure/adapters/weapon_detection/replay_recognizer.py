"""replay 入力の観測を返すブキ認識アダプタ。"""

from __future__ import annotations

import asyncio
import threading

from splat_replay.application.interfaces import (
    WeaponCandidateScore,
    WeaponDisplayDetectionResult,
    WeaponRecognitionPort,
    WeaponRecognitionResult,
    WeaponSlotResult,
)
from splat_replay.domain.models import Frame
from splat_replay.infrastructure.test_input import (
    REPLAY_WEAPON_SLOT_NAMES,
    ReplayWeaponSlotObservation,
    resolve_replay_weapon_recognition_observation,
)


def _to_four_tuple(items: list[str]) -> tuple[str, str, str, str]:
    """4要素のリストを固定長タプルへ変換する。"""
    if len(items) != 4:
        raise ValueError(f"Expected exactly 4 items, got {len(items)}")
    return (items[0], items[1], items[2], items[3])


class ReplayWeaponRecognitionAdapter(WeaponRecognitionPort):
    """fixture 由来の観測を既存のブキ認識ポートとして返す。"""

    def __init__(self) -> None:
        self._cancel_lock = threading.Lock()
        self._cancel_generation = 0

    def request_cancel(self) -> None:
        """進行中の判別要求を中断する。"""
        with self._cancel_lock:
            self._cancel_generation += 1

    def _capture_cancel_generation(self) -> int:
        with self._cancel_lock:
            return self._cancel_generation

    def _ensure_not_cancelled(self, cancel_generation: int) -> None:
        with self._cancel_lock:
            if cancel_generation != self._cancel_generation:
                raise asyncio.CancelledError(
                    "replay weapon recognition cancelled"
                )

    async def detect_weapon_display(self, frame: Frame) -> bool:
        return (await self.detect_weapon_display_details(frame)).is_visible

    async def detect_weapon_display_details(
        self,
        frame: Frame,
    ) -> WeaponDisplayDetectionResult:
        del frame
        cancel_generation = self._capture_cancel_generation()
        observation = resolve_replay_weapon_recognition_observation()
        self._ensure_not_cancelled(cancel_generation)
        matched_slots = sum(slot.matched for slot in observation.slots)
        matched_allies = sum(slot.matched for slot in observation.slots[:4])
        matched_enemies = sum(slot.matched for slot in observation.slots[4:])
        return WeaponDisplayDetectionResult(
            is_visible=observation.display.is_visible,
            should_recognize=observation.display.should_recognize,
            score=1.0 if observation.display.is_visible else 0.0,
            ally_reliable_slot_count=matched_allies,
            enemy_reliable_slot_count=matched_enemies,
            outline_matched_slots=matched_slots,
            outline_matched_ally_slots=matched_allies,
            outline_matched_enemy_slots=matched_enemies,
            outline_team_slots_reliable=matched_slots
            == len(REPLAY_WEAPON_SLOT_NAMES),
            reason="replay_observation",
        )

    async def recognize_weapons(
        self,
        frame: Frame,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        del frame, save_predict_weapons_output, battle_dir_name
        cancel_generation = self._capture_cancel_generation()
        observation = resolve_replay_weapon_recognition_observation()
        self._ensure_not_cancelled(cancel_generation)
        observation_by_slot = {
            slot_observation.slot: slot_observation
            for slot_observation in observation.slots
        }
        slot_results: dict[str, WeaponSlotResult] = {}
        for slot_name in REPLAY_WEAPON_SLOT_NAMES:
            if target_slots is not None and slot_name not in target_slots:
                if (
                    previous_results is not None
                    and slot_name in previous_results
                ):
                    slot_results[slot_name] = previous_results[slot_name]
                    continue
                slot_results[slot_name] = self._unknown_slot_result(slot_name)
                continue
            slot_results[slot_name] = self._slot_result(
                observation_by_slot[slot_name]
            )

        return WeaponRecognitionResult(
            allies=_to_four_tuple(
                [
                    slot_results[slot].predicted_weapon
                    for slot in REPLAY_WEAPON_SLOT_NAMES[:4]
                ]
            ),
            enemies=_to_four_tuple(
                [
                    slot_results[slot].predicted_weapon
                    for slot in REPLAY_WEAPON_SLOT_NAMES[4:]
                ]
            ),
            slot_results=tuple(
                slot_results[slot] for slot in REPLAY_WEAPON_SLOT_NAMES
            ),
            predict_weapons_output_dir=None,
        )

    async def save_predict_weapons_output(
        self,
        frame: Frame,
        slot_results: tuple[WeaponSlotResult, ...],
        battle_dir_name: str | None = None,
    ) -> str | None:
        """replay では診断用の実 CV 出力を生成しない。"""
        del frame, slot_results, battle_dir_name
        cancel_generation = self._capture_cancel_generation()
        self._ensure_not_cancelled(cancel_generation)
        return None

    @staticmethod
    def _slot_result(
        observation: ReplayWeaponSlotObservation,
    ) -> WeaponSlotResult:
        if not observation.matched:
            return WeaponSlotResult(
                slot=observation.slot,
                predicted_weapon=observation.weapon,
                is_unmatched=True,
                top_candidates=(),
                detected_score=0.0,
            )
        return WeaponSlotResult(
            slot=observation.slot,
            predicted_weapon=observation.weapon,
            is_unmatched=False,
            top_candidates=(
                WeaponCandidateScore(
                    weapon=observation.weapon,
                    score=1.0,
                    threshold=0.0,
                ),
            ),
            detected_score=1.0,
        )

    @staticmethod
    def _unknown_slot_result(slot_name: str) -> WeaponSlotResult:
        return WeaponSlotResult(
            slot=slot_name,
            predicted_weapon="不明",
            is_unmatched=True,
            top_candidates=(),
            detected_score=None,
        )
