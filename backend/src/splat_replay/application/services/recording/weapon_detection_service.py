"""ブキ判別の実行制御サービス。"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace
from typing import Literal

from splat_replay.application.interfaces import (
    EventBusPort,
    LoggerPort,
    WeaponCandidateScore,
    WeaponRecognitionPort,
    WeaponRecognitionResult,
    WeaponSlotResult,
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
DETECTION_RECOGNITION_TIMEOUT_SECONDS = 90.0
FINALIZE_RECOGNITION_TIMEOUT_SECONDS = 120.0
UNKNOWN_WEAPON_LABEL = "不明"
SLOT_COUNT = 8
SLOT_NAMES = (
    "ally_1",
    "ally_2",
    "ally_3",
    "ally_4",
    "enemy_1",
    "enemy_2",
    "enemy_3",
    "enemy_4",
)


_WeaponTaskKind = Literal["display_ng", "recognized", "finalized", "error"]


@dataclass(frozen=True)
class _WeaponTaskResult:
    """バックグラウンドタスクの処理結果。"""

    kind: _WeaponTaskKind
    generation: int
    battle_started_at: float
    elapsed_seconds: float
    recognition_result: WeaponRecognitionResult | None = None
    labels: list[str] | None = None
    best_scores: list[float] | None = None
    attempts: int = 0
    error: str | None = None
    error_event: str | None = None
    visible_frame: Frame | None = None
    skipped_report_no_visible_frame: bool = False


def _to_four_tuple(items: list[str]) -> tuple[str, str, str, str]:
    """4要素のリストを固定長タプルに変換する。型チェッカー用のヘルパー。"""
    if len(items) != 4:
        raise ValueError(f"Expected exactly 4 items, got {len(items)}")
    return (items[0], items[1], items[2], items[3])


class WeaponDetectionService:
    """ブキ判別実行と20秒制御を担当する。

    `request_cancel()` は即時復帰し、generation を進めて旧タスク結果を無効化する。
    """

    def __init__(
        self,
        recognizer: WeaponRecognitionPort,
        logger: LoggerPort,
        event_bus: EventBusPort,
    ) -> None:
        self._recognizer = recognizer
        self._logger = logger
        self._event_bus = event_bus
        self._generation = 0
        self._active_battle_started_at: float | None = None
        self._inflight_task: asyncio.Task[_WeaponTaskResult] | None = None
        self._pending_frame: Frame | None = None
        self._pending_elapsed_seconds = 0.0
        self._window_closed = False
        self._finalize_started = False
        self._unmatched_report_attempted = False

    def request_cancel(self) -> None:
        """実行中のブキ判別タスクを中断する（待機せず即時復帰）。"""
        self._request_recognizer_cancel()
        self._generation += 1
        self._cancel_inflight_task()
        self._pending_frame = None
        self._pending_elapsed_seconds = 0.0
        self._window_closed = False
        self._finalize_started = False
        self._unmatched_report_attempted = False

    async def process(
        self,
        *,
        frame: Frame,
        context: RecordingContext,
    ) -> RecordingContext:
        """ブキ判別を非ブロッキングで進め、完了結果のみ反映する。"""
        if context.battle_started_at <= 0.0:
            return context

        self._switch_battle_if_needed(context.battle_started_at)
        context = await self._drain_completed_task(context)

        if context.weapon_detection_done:
            return context

        elapsed = max(0.0, time.time() - context.battle_started_at)
        if elapsed > DETECTION_WINDOW_SECONDS:
            self._window_closed = True
        elif not self._window_closed:
            self._pending_frame = frame.copy()
            self._pending_elapsed_seconds = elapsed

        if self._inflight_task is None and self._pending_frame is not None:
            pending_frame = self._pending_frame
            pending_elapsed = self._pending_elapsed_seconds
            self._pending_frame = None
            self._pending_elapsed_seconds = 0.0
            self._start_detection_task(
                frame=pending_frame,
                context=context,
                elapsed_seconds=pending_elapsed,
            )

        if (
            self._window_closed
            and not self._finalize_started
            and self._inflight_task is None
            and self._pending_frame is None
            and not context.weapon_detection_done
        ):
            self._start_finalize_task(
                context=context,
                elapsed_seconds=elapsed,
            )

        return context

    def _switch_battle_if_needed(self, battle_started_at: float) -> None:
        if self._active_battle_started_at == battle_started_at:
            return
        if self._active_battle_started_at is not None:
            self._request_recognizer_cancel()
        self._generation += 1
        self._cancel_inflight_task()
        self._pending_frame = None
        self._pending_elapsed_seconds = 0.0
        self._window_closed = False
        self._finalize_started = False
        self._unmatched_report_attempted = False
        self._active_battle_started_at = battle_started_at

    def _request_recognizer_cancel(self) -> None:
        self._recognizer.request_cancel()

    def _cancel_inflight_task(self) -> None:
        inflight = self._inflight_task
        self._inflight_task = None
        if inflight is None:
            return
        if inflight.done():
            return
        inflight.cancel()

    async def _drain_completed_task(
        self,
        context: RecordingContext,
    ) -> RecordingContext:
        inflight = self._inflight_task
        if inflight is None or not inflight.done():
            return context
        self._inflight_task = None
        try:
            result = inflight.result()
        except asyncio.CancelledError:
            return context
        except Exception as exc:
            self._logger.warning(
                "ブキ判別バックグラウンドタスクに失敗しました",
                error=str(exc),
            )
            return context
        return self._apply_task_result(context=context, result=result)

    def _apply_task_result(
        self,
        *,
        context: RecordingContext,
        result: _WeaponTaskResult,
    ) -> RecordingContext:
        if result.generation != self._generation:
            return context
        if result.battle_started_at != context.battle_started_at:
            return context

        if result.error_event is not None and result.error is not None:
            self._logger.warning(result.error_event, error=result.error)
        if result.skipped_report_no_visible_frame:
            self._logger.info(
                "ブキ表示未検出のため未一致レポート出力をスキップ",
                elapsed_seconds=result.elapsed_seconds,
            )
        if result.visible_frame is not None:
            context = replace(
                context,
                weapon_last_visible_frame=result.visible_frame.copy(),
            )

        if result.kind == "display_ng":
            return context
        if result.kind == "error":
            return context
        if result.kind == "recognized":
            return self._apply_recognition_result(
                context=context,
                result=result,
            )
        if result.kind == "finalized":
            return self._apply_finalized_result(
                context=context,
                result=result,
            )
        return context

    def _start_detection_task(
        self,
        *,
        frame: Frame,
        context: RecordingContext,
        elapsed_seconds: float,
    ) -> None:
        self._inflight_task = asyncio.create_task(
            self._run_detection_task(
                frame=frame,
                context=context,
                generation=self._generation,
                battle_started_at=context.battle_started_at,
                elapsed_seconds=elapsed_seconds,
            )
        )

    def _start_finalize_task(
        self,
        *,
        context: RecordingContext,
        elapsed_seconds: float,
    ) -> None:
        self._finalize_started = True
        self._inflight_task = asyncio.create_task(
            self._run_finalize_task(
                context=context,
                generation=self._generation,
                battle_started_at=context.battle_started_at,
                elapsed_seconds=elapsed_seconds,
            )
        )

    async def _run_detection_task(
        self,
        *,
        frame: Frame,
        context: RecordingContext,
        generation: int,
        battle_started_at: float,
        elapsed_seconds: float,
    ) -> _WeaponTaskResult:
        try:
            is_visible = await self._recognizer.detect_weapon_display(frame)
        except Exception as exc:
            return _WeaponTaskResult(
                kind="error",
                generation=generation,
                battle_started_at=battle_started_at,
                elapsed_seconds=elapsed_seconds,
                error=str(exc),
                error_event="ブキ表示判定に失敗しました",
            )
        if not is_visible:
            return _WeaponTaskResult(
                kind="display_ng",
                generation=generation,
                battle_started_at=battle_started_at,
                elapsed_seconds=elapsed_seconds,
            )

        current_labels = _normalize_weapon_labels(context.metadata)
        target_slots = _get_unknown_slot_names(current_labels)

        # 既存の判定結果を収集
        previous_results = _build_previous_results(context)

        try:
            recognition_result = await asyncio.wait_for(
                self._recognizer.recognize_weapons(
                    frame,
                    save_unmatched_report=False,
                    target_slots=target_slots,
                    previous_results=previous_results,
                ),
                timeout=DETECTION_RECOGNITION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return _WeaponTaskResult(
                kind="error",
                generation=generation,
                battle_started_at=battle_started_at,
                elapsed_seconds=elapsed_seconds,
                error=(
                    "ブキ判別タイムアウト"
                    f" timeout_seconds={DETECTION_RECOGNITION_TIMEOUT_SECONDS}"
                ),
                error_event="ブキ判別がタイムアウトしました",
                visible_frame=frame.copy(),
            )
        except Exception as exc:
            return _WeaponTaskResult(
                kind="error",
                generation=generation,
                battle_started_at=battle_started_at,
                elapsed_seconds=elapsed_seconds,
                error=str(exc),
                error_event="ブキ判別に失敗しました",
                visible_frame=frame.copy(),
            )

        # 判別完了かつレポート未出力の場合、レポート出力用に再度呼び出す
        if (
            _is_result_complete(recognition_result)
            and not self._unmatched_report_attempted
        ):
            self._unmatched_report_attempted = True
            # 判別結果からprevious_resultsを構築
            result_by_slot = {
                slot_result.slot: slot_result
                for slot_result in recognition_result.slot_results
            }
            try:
                report_result = await asyncio.wait_for(
                    self._recognizer.recognize_weapons(
                        frame,
                        save_unmatched_report=True,
                        target_slots=set(),  # 再判別なし
                        previous_results=result_by_slot,
                    ),
                    timeout=FINALIZE_RECOGNITION_TIMEOUT_SECONDS,
                )
                # レポート出力の結果は無視（既に判別完了しているため）
                _ = report_result
            except asyncio.TimeoutError:
                self._logger.warning(
                    "ブキ判別レポートの保存がタイムアウトしました",
                    error=(
                        "ブキ判別タイムアウト"
                        f" timeout_seconds={FINALIZE_RECOGNITION_TIMEOUT_SECONDS}"
                    ),
                )
            except Exception as exc:
                self._logger.warning(
                    "ブキ判別レポートの保存に失敗しました",
                    error=str(exc),
                )

        return _WeaponTaskResult(
            kind="recognized",
            generation=generation,
            battle_started_at=battle_started_at,
            elapsed_seconds=elapsed_seconds,
            recognition_result=recognition_result,
            attempts=context.weapon_detection_attempts + 1,
            error_event=None,
            error=None,
            visible_frame=frame.copy(),
        )

    async def _run_finalize_task(
        self,
        *,
        context: RecordingContext,
        generation: int,
        battle_started_at: float,
        elapsed_seconds: float,
    ) -> _WeaponTaskResult:
        labels = _normalize_weapon_labels(context.metadata)
        best_scores = _normalize_best_scores(context.weapon_best_scores)
        finalize_warning: tuple[str, str] | None = None
        skipped_report_no_visible_frame = False

        if context.weapon_last_visible_frame is not None:
            target_slots = _get_unknown_slot_names(labels)
            save_unmatched_report = not self._unmatched_report_attempted
            if save_unmatched_report:
                self._unmatched_report_attempted = True

            # 既存の判定結果を収集（レポート出力用）
            previous_results = _build_previous_results(context)

            try:
                final_result = await asyncio.wait_for(
                    self._recognizer.recognize_weapons(
                        context.weapon_last_visible_frame,
                        save_unmatched_report=save_unmatched_report,
                        target_slots=target_slots if target_slots else None,
                        previous_results=previous_results,
                    ),
                    timeout=FINALIZE_RECOGNITION_TIMEOUT_SECONDS,
                )
                for slot_result in final_result.slot_results:
                    index = SLOT_NAMES.index(slot_result.slot)
                    best_scores[index] = max(
                        best_scores[index], slot_result.best_score
                    )
                    if not slot_result.is_unmatched:
                        labels[index] = slot_result.predicted_weapon
            except asyncio.TimeoutError:
                finalize_warning = (
                    "最終ブキ判別レポートの保存がタイムアウトしました",
                    (
                        "最終ブキ判別タイムアウト"
                        f" timeout_seconds={FINALIZE_RECOGNITION_TIMEOUT_SECONDS}"
                    ),
                )
            except Exception as exc:
                finalize_warning = (
                    "最終ブキ判別レポートの保存に失敗しました",
                    str(exc),
                )
        elif _has_unknown_slots(labels):
            skipped_report_no_visible_frame = True

        for index in range(SLOT_COUNT):
            if labels[index]:
                continue
            labels[index] = UNKNOWN_WEAPON_LABEL
            if best_scores[index] < 0.0:
                best_scores[index] = -1.0

        warning_event = None
        warning_error = None
        if finalize_warning is not None:
            warning_event, warning_error = finalize_warning

        return _WeaponTaskResult(
            kind="finalized",
            generation=generation,
            battle_started_at=battle_started_at,
            elapsed_seconds=elapsed_seconds,
            labels=labels,
            best_scores=best_scores,
            attempts=context.weapon_detection_attempts,
            error_event=warning_event,
            error=warning_error,
            skipped_report_no_visible_frame=skipped_report_no_visible_frame,
        )

    def _apply_recognition_result(
        self,
        *,
        context: RecordingContext,
        result: _WeaponTaskResult,
    ) -> RecordingContext:
        recognition_result = result.recognition_result
        if recognition_result is None:
            return context

        attempts = result.attempts
        next_best_scores = _normalize_best_scores(context.weapon_best_scores)
        current_labels = _normalize_weapon_labels(context.metadata)

        # 既存のweapon_slot_resultsを取得または初期化
        slot_results_by_slot: dict[str, WeaponSlotResult] = {}
        if context.weapon_slot_results:
            slot_results_by_slot = {
                sr.slot: sr for sr in context.weapon_slot_results
            }

        for slot_result in recognition_result.slot_results:
            index = SLOT_NAMES.index(slot_result.slot)
            previous_best = next_best_scores[index]
            current_best = slot_result.best_score
            if current_best <= previous_best + 1e-12:
                continue
            next_best_scores[index] = current_best
            next_label = slot_result.predicted_weapon
            current_labels[index] = next_label
            # slot_resultsを更新
            slot_results_by_slot[slot_result.slot] = slot_result

        allies = _to_four_tuple(current_labels[:4])
        enemies = _to_four_tuple(current_labels[4:])
        updated_metadata = replace(
            context.metadata,
            allies=allies,
            enemies=enemies,
        )
        done = not _has_unknown_slots(current_labels)
        visible_frame = result.visible_frame

        # weapon_slot_resultsをタプルに変換（SLOT_NAMESの順序で）
        updated_slot_results = tuple(
            slot_results_by_slot.get(
                slot,
                WeaponSlotResult(
                    slot=slot,
                    predicted_weapon=current_labels[i],
                    is_unmatched=(
                        not current_labels[i]
                        or current_labels[i] == UNKNOWN_WEAPON_LABEL
                    ),
                    top_candidates=(),
                ),
            )
            for i, slot in enumerate(SLOT_NAMES)
        )

        updated_context = replace(
            context,
            metadata=updated_metadata,
            weapon_detection_attempts=attempts,
            weapon_best_scores=tuple(next_best_scores),
            weapon_slot_results=updated_slot_results,
            weapon_detection_done=done,
            weapon_last_visible_frame=(
                visible_frame.copy() if visible_frame is not None else None
            ),
        )

        if done:
            self._publish_updates(
                metadata=updated_metadata,
                allies=allies,
                enemies=enemies,
                elapsed_seconds=result.elapsed_seconds,
                attempts=attempts,
                is_final=done,
            )
        if done:
            self._pending_frame = None
            self._window_closed = True
            self._finalize_started = True
        return updated_context

    def _apply_finalized_result(
        self,
        *,
        context: RecordingContext,
        result: _WeaponTaskResult,
    ) -> RecordingContext:
        labels = result.labels
        best_scores = result.best_scores
        if labels is None or best_scores is None:
            return context

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
        self._pending_frame = None
        self._window_closed = True
        self._finalize_started = True
        self._publish_updates(
            metadata=updated_metadata,
            allies=allies,
            enemies=enemies,
            elapsed_seconds=result.elapsed_seconds,
            attempts=result.attempts,
            is_final=True,
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
    ) -> None:
        self._logger.info(
            "ブキ検知結果を更新しました",
            allies=list(allies),
            enemies=list(enemies),
            elapsed_seconds=elapsed_seconds,
            attempts=attempts,
            is_final=is_final,
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


def _is_result_complete(result: WeaponRecognitionResult) -> bool:
    """WeaponRecognitionResultが全スロット判別完了かどうかを返す。"""
    return all(
        not slot_result.is_unmatched for slot_result in result.slot_results
    )


def _get_unknown_slot_names(labels: list[str]) -> set[str]:
    """未判明のスロット名のセットを返す。"""
    unknown_slots = set()
    for index, label in enumerate(labels):
        if (not label) or label == UNKNOWN_WEAPON_LABEL:
            unknown_slots.add(SLOT_NAMES[index])
    return unknown_slots


def _build_previous_results(
    context: RecordingContext,
) -> dict[str, WeaponSlotResult]:
    """既存の判別結果を構築する。"""
    # weapon_slot_resultsが保存されていればそれを使用
    if context.weapon_slot_results:
        return {sr.slot: sr for sr in context.weapon_slot_results}

    # 保存されていない場合は従来の方法で復元（後方互換性）
    labels = _normalize_weapon_labels(context.metadata)
    best_scores = _normalize_best_scores(context.weapon_best_scores)
    results: dict[str, WeaponSlotResult] = {}
    for index, slot in enumerate(SLOT_NAMES):
        label = labels[index]
        score = best_scores[index]
        if label and label != UNKNOWN_WEAPON_LABEL:
            # 判別済みスロット（threshold情報はない）
            top_candidates = (
                (
                    WeaponCandidateScore(
                        weapon=label, score=score, threshold=0.0
                    ),
                )
                if score >= 0.0
                else ()
            )
            results[slot] = WeaponSlotResult(
                slot=slot,
                predicted_weapon=label,
                is_unmatched=False,
                top_candidates=top_candidates,
            )
        else:
            # 未判別スロット
            results[slot] = WeaponSlotResult(
                slot=slot,
                predicted_weapon=UNKNOWN_WEAPON_LABEL,
                is_unmatched=True,
                top_candidates=(),
            )
    return results
