"""ブキ判別の実行制御サービス。"""

from __future__ import annotations

import time
from dataclasses import replace

from splat_replay.application.interfaces import (
    EventBusPort,
    LoggerPort,
    WeaponRecognitionPort,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.domain.events import (
    BattleWeaponsDetected,
    RecordingMetadataUpdated,
)
from splat_replay.domain.models import Frame, RecordingMetadata

DETECTION_WINDOW_SECONDS = 20.0
UNKNOWN_WEAPON_LABEL = "不明"
SLOT_COUNT = 8


def _to_four_tuple(items: list[str]) -> tuple[str, str, str, str]:
    """4要素のリストを固定長タプルに変換する。型チェッカー用のヘルパー。"""
    if len(items) != 4:
        raise ValueError(f"Expected exactly 4 items, got {len(items)}")
    return (items[0], items[1], items[2], items[3])


class WeaponDetectionService:
    """ブキ判別実行と20秒制御を担当する。"""

    def __init__(
        self,
        recognizer: WeaponRecognitionPort,
        logger: LoggerPort,
        event_bus: EventBusPort,
    ) -> None:
        self._recognizer = recognizer
        self._logger = logger
        self._event_bus = event_bus

    async def process(
        self,
        *,
        frame: Frame,
        context: RecordingContext,
    ) -> RecordingContext:
        """ブキ判別を実行し、必要な場合のみContextを更新する。"""
        if context.weapon_detection_done or context.battle_started_at <= 0.0:
            return context

        elapsed = max(0.0, time.time() - context.battle_started_at)
        if elapsed > DETECTION_WINDOW_SECONDS:
            return await self._finalize(
                context=context,
                elapsed_seconds=elapsed,
            )

        is_visible = await self._recognizer.detect_weapon_display(frame)
        if not is_visible:
            return context

        try:
            recognition_result = await self._recognizer.recognize_weapons(
                frame,
                save_unmatched_report=False,
            )
        except Exception as exc:
            self._logger.warning(
                "ブキ判別に失敗しました",
                error=str(exc),
            )
            return context

        attempts = context.weapon_detection_attempts + 1
        next_best_scores = _normalize_best_scores(context.weapon_best_scores)
        current_labels = _normalize_weapon_labels(context.metadata)
        labels_changed = False

        for index, slot_result in enumerate(recognition_result.slot_results):
            previous_best = next_best_scores[index]
            current_best = slot_result.best_score
            if current_best <= previous_best + 1e-12:
                continue
            next_best_scores[index] = current_best
            next_label = slot_result.predicted_weapon
            if current_labels[index] != next_label:
                current_labels[index] = next_label
                labels_changed = True

        allies = _to_four_tuple(current_labels[:4])
        enemies = _to_four_tuple(current_labels[4:])
        updated_metadata = replace(
            context.metadata,
            allies=allies,
            enemies=enemies,
        )
        done = not _has_unknown_slots(current_labels)
        updated_context = replace(
            context,
            metadata=updated_metadata,
            weapon_detection_attempts=attempts,
            weapon_best_scores=tuple(next_best_scores),
            weapon_detection_done=done,
            weapon_last_visible_frame=frame.copy(),
        )

        if labels_changed or done:
            self._publish_updates(
                metadata=updated_metadata,
                allies=allies,
                enemies=enemies,
                elapsed_seconds=elapsed,
                attempts=attempts,
                is_final=done,
                unmatched_output_dir=None,
            )
        return updated_context

    async def _finalize(
        self,
        *,
        context: RecordingContext,
        elapsed_seconds: float,
    ) -> RecordingContext:
        labels = _normalize_weapon_labels(context.metadata)
        best_scores = _normalize_best_scores(context.weapon_best_scores)
        unmatched_output_dir: str | None = None

        if (
            _has_unknown_slots(labels)
            and context.weapon_last_visible_frame is not None
        ):
            try:
                final_result = await self._recognizer.recognize_weapons(
                    context.weapon_last_visible_frame,
                    save_unmatched_report=True,
                )
                unmatched_output_dir = final_result.unmatched_output_dir
                for index, slot_result in enumerate(final_result.slot_results):
                    best_scores[index] = max(
                        best_scores[index], slot_result.best_score
                    )
                    if not slot_result.is_unmatched:
                        labels[index] = slot_result.predicted_weapon
            except Exception as exc:
                self._logger.warning(
                    "最終ブキ判別レポートの保存に失敗しました",
                    error=str(exc),
                )
        elif _has_unknown_slots(labels):
            self._logger.info(
                "ブキ表示未検出のため未一致レポート出力をスキップ",
                elapsed_seconds=elapsed_seconds,
            )

        for index in range(SLOT_COUNT):
            if labels[index]:
                continue
            labels[index] = UNKNOWN_WEAPON_LABEL
            if best_scores[index] < 0.0:
                best_scores[index] = -1.0

        allies = _to_four_tuple(labels[:4])
        enemies = _to_four_tuple(labels[4:])
        updated_metadata = replace(
            context.metadata, allies=allies, enemies=enemies
        )
        updated_context = replace(
            context,
            metadata=updated_metadata,
            weapon_best_scores=tuple(best_scores),
            weapon_detection_done=True,
            weapon_last_visible_frame=None,
        )
        self._publish_updates(
            metadata=updated_metadata,
            allies=allies,
            enemies=enemies,
            elapsed_seconds=elapsed_seconds,
            attempts=context.weapon_detection_attempts,
            is_final=True,
            unmatched_output_dir=unmatched_output_dir,
        )
        return updated_context

    def _publish_updates(
        self,
        *,
        metadata: RecordingMetadata,
        allies: tuple[str, str, str, str],
        enemies: tuple[str, str, str, str],
        elapsed_seconds: float,
        attempts: int,
        is_final: bool,
        unmatched_output_dir: str | None,
    ) -> None:
        self._logger.info(
            "ブキ検知結果を更新しました",
            allies=list(allies),
            enemies=list(enemies),
            elapsed_seconds=elapsed_seconds,
            attempts=attempts,
            is_final=is_final,
            unmatched_output_dir=unmatched_output_dir,
        )
        self._event_bus.publish_domain_event(
            RecordingMetadataUpdated(metadata=metadata.to_dict())
        )
        self._event_bus.publish_domain_event(
            BattleWeaponsDetected(
                allies=list(allies),
                enemies=list(enemies),
                elapsed_seconds=elapsed_seconds,
                attempt=attempts,
                is_final=is_final,
                unmatched_output_dir=unmatched_output_dir,
            )
        )


def _normalize_best_scores(
    best_scores: tuple[float, ...] | None,
) -> list[float]:
    if best_scores is None:
        return [-1.0] * SLOT_COUNT
    scores = list(best_scores[:SLOT_COUNT])
    if len(scores) < SLOT_COUNT:
        scores.extend([-1.0] * (SLOT_COUNT - len(scores)))
    return scores


def _normalize_weapon_labels(metadata: RecordingMetadata) -> list[str]:
    labels: list[str] = []
    if metadata.allies is not None:
        labels.extend(list(metadata.allies[:4]))
    if len(labels) < 4:
        labels.extend([""] * (4 - len(labels)))

    enemies: list[str] = []
    if metadata.enemies is not None:
        enemies.extend(list(metadata.enemies[:4]))
    if len(enemies) < 4:
        enemies.extend([""] * (4 - len(enemies)))

    return labels + enemies


def _has_unknown_slots(labels: list[str]) -> bool:
    return any(
        (not label) or label == UNKNOWN_WEAPON_LABEL for label in labels
    )
