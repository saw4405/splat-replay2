"""ブキ判別の実行制御サービス。"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Callable, Coroutine, Literal, TypeVar

from splat_replay.application.interfaces import (
    ClockPort,
    EventBusPort,
    LoggerPort,
    WeaponCandidateScore,
    WeaponDisplayDetectionResult,
    WeaponRecognitionPort,
    WeaponRecognitionResult,
    WeaponSlotResult,
)
from splat_replay.application.metadata import recording_metadata_to_dict
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.domain.events import (
    BattleWeaponsDetected,
    RecordingMetadataUpdated,
)
from splat_replay.domain.models import Frame, RecordingMetadata

DETECTION_WINDOW_SECONDS = 30.0
DETECTION_RECOGNITION_TIMEOUT_SECONDS = 90.0
FINALIZE_RECOGNITION_TIMEOUT_SECONDS = 120.0
DISPLAY_CHECK_INTERVAL_SECONDS = 0.25
VISIBLE_CANDIDATE_BUFFER_SIZE = 5
SAMPLED_FRAME_BUFFER_SIZE = 3
SAMPLED_FRAME_INTERVAL_SECONDS = 0.25
FALLBACK_FRAME_BUFFER_SIZE = 40
FALLBACK_FRAME_INTERVAL_SECONDS = 1.0
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
_T = TypeVar("_T")


class _WallClock:
    def now(self) -> float:
        return time.time()


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
    display_check_completed: bool = False
    display_visible: bool = False
    skipped_predict_weapons_output_no_visible_frame: bool = False
    saved_predict_weapons_output_from_diagnostic_frame: bool = False
    diagnostic_frame: Frame | None = None
    display_details: WeaponDisplayDetectionResult | None = None
    report_frame: Frame | None = None
    report_slot_results: tuple[WeaponSlotResult, ...] | None = None


@dataclass(frozen=True)
class _QueuedFrame:
    frame: Frame
    elapsed_seconds: float


@dataclass(frozen=True)
class _DisplayDiagnostic:
    frame: Frame
    elapsed_seconds: float
    details: WeaponDisplayDetectionResult


def _to_four_tuple(items: list[str]) -> tuple[str, str, str, str]:
    """4要素のリストを固定長タプルに変換する。型チェッカー用のヘルパー。"""
    if len(items) != 4:
        raise ValueError(f"Expected exactly 4 items, got {len(items)}")
    return (items[0], items[1], items[2], items[3])


class WeaponDetectionService:
    """ブキ判別実行と検出窓の制御を担当する。

    `request_cancel()` は即時復帰し、generation を進めて旧タスク結果を無効化する。
    """

    def __init__(
        self,
        recognizer: WeaponRecognitionPort,
        logger: LoggerPort,
        event_bus: EventBusPort,
        detection_window_seconds: float = DETECTION_WINDOW_SECONDS,
        clock: ClockPort | None = None,
    ) -> None:
        self._recognizer = recognizer
        self._logger = logger
        self._event_bus = event_bus
        self._detection_window_seconds = detection_window_seconds
        self._clock = clock or _WallClock()
        self._generation = 0
        self._active_battle_started_at: float | None = None
        self._inflight_task: asyncio.Task[_WeaponTaskResult] | None = None
        self._report_output_task: asyncio.Task[None] | None = None
        self._pending_frame: Frame | None = None
        self._pending_elapsed_seconds = 0.0
        self._sampled_frames: deque[_QueuedFrame] = deque(
            maxlen=SAMPLED_FRAME_BUFFER_SIZE
        )
        self._fallback_frames: deque[_QueuedFrame] = deque(
            maxlen=FALLBACK_FRAME_BUFFER_SIZE
        )
        self._visible_candidates: deque[Frame] = deque(
            maxlen=VISIBLE_CANDIDATE_BUFFER_SIZE
        )
        self._last_display_diagnostic: _DisplayDiagnostic | None = None
        self._last_detection_started_at: float | None = None
        self._last_sampled_at: float | None = None
        self._last_fallback_sampled_at: float | None = None
        self._display_check_count = 0
        self._visible_hit_count = 0
        self._window_closed = False
        self._finalize_started = False
        self._predict_weapons_output_attempted = False

    def request_cancel(self) -> None:
        """実行中のブキ判別タスクを中断する（待機せず即時復帰）。"""
        self._request_recognizer_cancel()
        self._generation += 1
        self._cancel_inflight_task()
        self._cancel_report_output_task()
        self._reset_frame_buffers()
        self._reset_detection_statistics()
        self._window_closed = False
        self._finalize_started = False
        self._predict_weapons_output_attempted = False

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
        self._cleanup_report_output_task()
        context = await self._drain_completed_task(context)

        context = _mark_detection_done_if_all_slots_known(context)
        if context.weapon_detection_done:
            return context

        now = self._clock.now()
        elapsed = max(0.0, now - context.battle_started_at)
        if elapsed > self._detection_window_seconds:
            self._window_closed = True
        elif not self._window_closed:
            self._sample_fallback_frame_if_needed(
                frame=frame,
                elapsed_seconds=elapsed,
                now=now,
            )
            self._pending_frame = frame.copy()
            self._pending_elapsed_seconds = elapsed
            if self._inflight_task is not None:
                self._sample_frame_if_needed(
                    frame=frame,
                    elapsed_seconds=elapsed,
                    now=now,
                )

        if self._inflight_task is None:
            if self._can_start_detection(now=now):
                next_frame = self._pop_next_detection_frame()
                if next_frame is not None:
                    self._start_detection_task(
                        frame=next_frame.frame,
                        context=context,
                        elapsed_seconds=next_frame.elapsed_seconds,
                        now=now,
                    )

        if (
            self._window_closed
            and not self._finalize_started
            and self._inflight_task is None
            and not self._has_pending_detection_frames()
            and not context.weapon_detection_done
        ):
            context = self.complete_as_unknown(
                context=context,
                elapsed_seconds=elapsed,
            )

        return context

    async def finalize_for_finish(
        self,
        *,
        frame: Frame,
        context: RecordingContext,
    ) -> RecordingContext:
        """バトル終了検知時に、ブキ判別を `null` のまま残さないよう確定する。"""
        if context.battle_started_at <= 0.0:
            return context

        self._switch_battle_if_needed(context.battle_started_at)
        self._cleanup_report_output_task()
        context = await self._drain_completed_task(context)

        context = _mark_detection_done_if_all_slots_known(context)
        if context.weapon_detection_done:
            return context

        if self._inflight_task is not None:
            self._request_recognizer_cancel()
            self._cancel_inflight_task()

        elapsed = max(0.0, self._clock.now() - context.battle_started_at)
        self._window_closed = True
        self._finalize_started = True
        result = await self._run_finalize_task(
            context=context,
            generation=self._generation,
            battle_started_at=context.battle_started_at,
            elapsed_seconds=elapsed,
            diagnostic_frame=frame,
        )
        return self._apply_task_result(context=context, result=result)

    def complete_as_unknown(
        self,
        *,
        context: RecordingContext,
        elapsed_seconds: float | None = None,
    ) -> RecordingContext:
        """譛ｪ遒ｺ螳壹せ繝ｭ繝・ヨ繧剃ｸ肴・縺ｧ遒ｺ螳壹＠縲∵眠隕上・蛻､蛻･蜃ｦ逅・ｯ髢句ｧ九＠縺ｪ縺・・"""
        if context.battle_started_at <= 0.0:
            return context

        self._switch_battle_if_needed(context.battle_started_at)
        self._cleanup_report_output_task()

        context = _mark_detection_done_if_all_slots_known(context)
        if context.weapon_detection_done:
            return context

        labels = _normalize_weapon_labels(context.metadata)
        best_scores = _normalize_best_scores(context.weapon_best_scores)
        for index in range(SLOT_COUNT):
            if not _is_unknown_weapon_label(labels[index]):
                continue
            labels[index] = UNKNOWN_WEAPON_LABEL
            if best_scores[index] < 0.0:
                best_scores[index] = -1.0
        report_frame: Frame | None = None
        report_slot_results: tuple[WeaponSlotResult, ...] | None = None
        saved_predict_weapons_output_from_diagnostic_frame = False
        display_details: WeaponDisplayDetectionResult | None = None
        if (
            self._display_check_count > 0
            and self._visible_hit_count == 0
            and self._last_display_diagnostic is not None
            and not self._predict_weapons_output_attempted
        ):
            report_frame = self._last_display_diagnostic.frame.copy()
            slot_results_by_slot = _build_slot_results_from_labels(
                labels,
                best_scores,
            )
            report_slot_results = tuple(
                slot_results_by_slot[slot] for slot in SLOT_NAMES
            )
            saved_predict_weapons_output_from_diagnostic_frame = True
            display_details = self._last_display_diagnostic.details

        elapsed = (
            elapsed_seconds
            if elapsed_seconds is not None
            else max(0.0, self._clock.now() - context.battle_started_at)
        )
        result = _WeaponTaskResult(
            kind="finalized",
            generation=self._generation,
            battle_started_at=context.battle_started_at,
            elapsed_seconds=elapsed,
            labels=labels,
            best_scores=best_scores,
            attempts=context.weapon_detection_attempts,
            saved_predict_weapons_output_from_diagnostic_frame=(
                saved_predict_weapons_output_from_diagnostic_frame
            ),
            diagnostic_frame=report_frame,
            display_details=display_details,
            report_frame=report_frame,
            report_slot_results=report_slot_results,
        )
        return self._apply_task_result(context=context, result=result)

    def _switch_battle_if_needed(self, battle_started_at: float) -> None:
        if self._active_battle_started_at == battle_started_at:
            return
        if self._active_battle_started_at is not None:
            self._request_recognizer_cancel()
        self._generation += 1
        self._cancel_inflight_task()
        self._cancel_report_output_task()
        self._reset_frame_buffers()
        self._reset_detection_statistics()
        self._window_closed = False
        self._finalize_started = False
        self._predict_weapons_output_attempted = False
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

    def _cancel_report_output_task(self) -> None:
        report_task = self._report_output_task
        self._report_output_task = None
        if report_task is None:
            return
        if report_task.done():
            return
        report_task.cancel()

    def _cleanup_report_output_task(self) -> None:
        report_task = self._report_output_task
        if report_task is not None and report_task.done():
            self._report_output_task = None

    async def _run_recognizer_call(
        self,
        factory: Callable[[], Coroutine[Any, Any, _T]],
    ) -> _T:
        """CPU負荷の高い recognizer 呼び出しをワーカースレッドへ逃がす。"""

        def _run_in_worker_thread() -> _T:
            return asyncio.run(factory())

        return await asyncio.to_thread(_run_in_worker_thread)

    async def _detect_weapon_display_details(
        self,
        frame: Frame,
    ) -> WeaponDisplayDetectionResult:
        detector = getattr(
            self._recognizer,
            "detect_weapon_display_details",
            None,
        )
        if callable(detector):
            return await detector(frame)

        is_visible = await self._recognizer.detect_weapon_display(frame)
        return WeaponDisplayDetectionResult(
            is_visible=is_visible,
            should_recognize=is_visible,
            score=1.0 if is_visible else 0.0,
            reason="legacy_bool",
        )

    def _reset_frame_buffers(self) -> None:
        self._pending_frame = None
        self._pending_elapsed_seconds = 0.0
        self._sampled_frames.clear()
        self._fallback_frames.clear()
        self._visible_candidates.clear()
        self._last_display_diagnostic = None
        self._last_detection_started_at = None
        self._last_sampled_at = None
        self._last_fallback_sampled_at = None

    def _reset_detection_statistics(self) -> None:
        self._display_check_count = 0
        self._visible_hit_count = 0

    def _sample_fallback_frame_if_needed(
        self,
        *,
        frame: Frame,
        elapsed_seconds: float,
        now: float,
    ) -> None:
        if (
            self._last_fallback_sampled_at is not None
            and now - self._last_fallback_sampled_at
            < FALLBACK_FRAME_INTERVAL_SECONDS
        ):
            return
        self._fallback_frames.append(
            _QueuedFrame(frame=frame.copy(), elapsed_seconds=elapsed_seconds)
        )
        self._last_fallback_sampled_at = now

    def _sample_frame_if_needed(
        self,
        *,
        frame: Frame,
        elapsed_seconds: float,
        now: float,
    ) -> None:
        if (
            self._last_sampled_at is not None
            and now - self._last_sampled_at < SAMPLED_FRAME_INTERVAL_SECONDS
        ):
            return
        self._sampled_frames.append(
            _QueuedFrame(frame=frame.copy(), elapsed_seconds=elapsed_seconds)
        )
        self._last_sampled_at = now

    def _pop_next_detection_frame(self) -> _QueuedFrame | None:
        if self._sampled_frames:
            return self._sampled_frames.popleft()
        if self._pending_frame is None:
            return None
        queued = _QueuedFrame(
            frame=self._pending_frame,
            elapsed_seconds=self._pending_elapsed_seconds,
        )
        self._pending_frame = None
        self._pending_elapsed_seconds = 0.0
        return queued

    def _can_start_detection(self, *, now: float) -> bool:
        if self._window_closed:
            return True
        if self._last_detection_started_at is None:
            return True
        return (
            now - self._last_detection_started_at
            >= DISPLAY_CHECK_INTERVAL_SECONDS
        )

    def _has_pending_detection_frames(self) -> bool:
        return self._pending_frame is not None or bool(self._sampled_frames)

    def _remember_visible_candidate(self, frame: Frame) -> None:
        self._visible_candidates.append(frame.copy())

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
        if result.display_check_completed:
            self._display_check_count += 1
        if result.display_visible:
            self._visible_hit_count += 1
        if (
            result.display_check_completed
            and not result.display_visible
            and result.diagnostic_frame is not None
            and result.display_details is not None
        ):
            self._last_display_diagnostic = _DisplayDiagnostic(
                frame=result.diagnostic_frame.copy(),
                elapsed_seconds=result.elapsed_seconds,
                details=result.display_details,
            )

        if result.error_event is not None and result.error is not None:
            self._logger.warning(result.error_event, error=result.error)
        if result.visible_frame is not None:
            self._remember_visible_candidate(result.visible_frame)

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
            # _apply_finalized_result が _reset_detection_statistics() を呼ぶため、
            # スキップログ用のカウントを事前に保存する。
            display_check_count = self._display_check_count
            visible_hit_count = self._visible_hit_count
            context = self._apply_finalized_result(
                context=context,
                result=result,
            )
            # finalize 処理の後にスキップログを出すことで、
            # 「ブキ検知結果を更新しました」より後に記録されるようにする。
            if result.skipped_predict_weapons_output_no_visible_frame:
                self._logger.info(
                    "ブキ表示未検出のため predict_weapons 出力をスキップ",
                    elapsed_seconds=result.elapsed_seconds,
                    display_check_count=display_check_count,
                    visible_hit_count=visible_hit_count,
                )
            elif result.saved_predict_weapons_output_from_diagnostic_frame:
                self._logger.info(
                    "ブキ表示診断メトリクス",
                    elapsed_seconds=result.elapsed_seconds,
                    display_check_count=display_check_count,
                    visible_hit_count=visible_hit_count,
                    **_display_details_log_fields(result.display_details),
                )
                self._logger.info(
                    "表示未検出フレームの predict_weapons 出力を保存しました",
                    elapsed_seconds=result.elapsed_seconds,
                    display_check_count=display_check_count,
                    visible_hit_count=visible_hit_count,
                )
            else:
                self._logger.info(
                    "ブキ判別ウィンドウ統計",
                    display_check_count=display_check_count,
                    visible_hit_count=visible_hit_count,
                    elapsed_seconds=result.elapsed_seconds,
                )
            return context
        return context

    def _start_detection_task(
        self,
        *,
        frame: Frame,
        context: RecordingContext,
        elapsed_seconds: float,
        now: float,
    ) -> None:
        self._last_detection_started_at = now
        self._inflight_task = asyncio.create_task(
            self._run_detection_task(
                frame=frame,
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
            display_details = await self._run_recognizer_call(
                lambda: self._detect_weapon_display_details(frame)
            )
        except Exception as exc:
            return _WeaponTaskResult(
                kind="error",
                generation=generation,
                battle_started_at=battle_started_at,
                elapsed_seconds=elapsed_seconds,
                error=str(exc),
                error_event="ブキ表示判定に失敗しました",
            )
        if not display_details.should_recognize:
            self._logger.debug(
                "ブキ表示なし",
                elapsed_seconds=elapsed_seconds,
            )
            return _WeaponTaskResult(
                kind="display_ng",
                generation=generation,
                battle_started_at=battle_started_at,
                elapsed_seconds=elapsed_seconds,
                display_check_completed=True,
                diagnostic_frame=frame.copy(),
                display_details=display_details,
            )

        self._logger.info(
            "ブキ表示を検出",
            elapsed_seconds=elapsed_seconds,
        )
        current_labels = _normalize_weapon_labels(context.metadata)
        target_slots = _get_unknown_slot_names(current_labels)

        # 既存の判定結果を収集
        previous_results = _build_previous_results(context)

        try:
            recognition_result = await asyncio.wait_for(
                self._run_recognizer_call(
                    lambda: self._recognizer.recognize_weapons(
                        frame,
                        save_predict_weapons_output=False,
                        target_slots=target_slots,
                        previous_results=previous_results,
                    )
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
                display_check_completed=True,
                display_visible=display_details.should_recognize,
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
                display_check_completed=True,
                display_visible=display_details.should_recognize,
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
            display_check_completed=True,
            display_visible=display_details.should_recognize,
        )

    async def _run_finalize_task(
        self,
        *,
        context: RecordingContext,
        generation: int,
        battle_started_at: float,
        elapsed_seconds: float,
        diagnostic_frame: Frame | None = None,
    ) -> _WeaponTaskResult:
        labels = _normalize_weapon_labels(context.metadata)
        best_scores = _normalize_best_scores(context.weapon_best_scores)
        finalize_warning: tuple[str, str] | None = None
        skipped_predict_weapons_output_no_visible_frame = False
        saved_predict_weapons_output_from_diagnostic_frame = False
        report_frame: Frame | None = None
        report_slot_results: tuple[WeaponSlotResult, ...] | None = None

        candidate_frames = list(reversed(self._visible_candidates))
        fallback_frames = list(reversed(self._fallback_frames))
        unknown_slots = _get_unknown_slot_names(labels)
        self._logger.info(
            "ブキ判別ファイナライズ開始",
            candidate_frame_count=len(candidate_frames),
            fallback_frame_count=len(fallback_frames),
            unknown_slot_count=len(unknown_slots),
            unknown_slots=sorted(unknown_slots),
        )
        if candidate_frames:
            should_save_report = not self._predict_weapons_output_attempted
            previous_results = _build_previous_results(context)

            for candidate_frame in candidate_frames:
                target_slots = _get_unknown_slot_names(labels)
                if not target_slots:
                    break
                try:
                    final_result = await asyncio.wait_for(
                        self._run_recognizer_call(
                            lambda: self._recognizer.recognize_weapons(
                                candidate_frame,
                                save_predict_weapons_output=False,
                                target_slots=target_slots,
                                previous_results=previous_results,
                                battle_dir_name=None,
                            )
                        ),
                        timeout=FINALIZE_RECOGNITION_TIMEOUT_SECONDS,
                    )
                    for slot_result in final_result.slot_results:
                        index = SLOT_NAMES.index(slot_result.slot)
                        best_scores[index] = max(
                            best_scores[index], slot_result.best_score
                        )
                        previous_results[slot_result.slot] = slot_result
                        if not slot_result.is_unmatched:
                            labels[index] = slot_result.predicted_weapon
                    if should_save_report:
                        report_frame = candidate_frame.copy()
                        report_slot_results = final_result.slot_results
                except asyncio.TimeoutError:
                    finalize_warning = (
                        "最終ブキ判別がタイムアウトしました",
                        (
                            "最終ブキ判別タイムアウト"
                            f" timeout_seconds={FINALIZE_RECOGNITION_TIMEOUT_SECONDS}"
                        ),
                    )
                    break
                except Exception as exc:
                    finalize_warning = (
                        "最終ブキ判別に失敗しました",
                        str(exc),
                    )
        elif fallback_frames and _has_unknown_slots(labels):
            should_save_report = not self._predict_weapons_output_attempted
            previous_results = _build_previous_results(context)

            fallback_frame_count = len(fallback_frames)
            for fallback_frame_index, queued_frame in enumerate(
                fallback_frames,
                start=1,
            ):
                target_slots = _get_unknown_slot_names(labels)
                if not target_slots:
                    break
                try:
                    self._logger.info(
                        "終了時fallbackブキ表示判定開始",
                        fallback_frame_index=fallback_frame_index,
                        fallback_frame_count=fallback_frame_count,
                        frame_elapsed_seconds=queued_frame.elapsed_seconds,
                        target_slot_count=len(target_slots),
                        target_slots=sorted(target_slots),
                    )
                    is_visible = await asyncio.wait_for(
                        self._run_recognizer_call(
                            lambda: self._recognizer.detect_weapon_display(
                                queued_frame.frame
                            )
                        ),
                        timeout=FINALIZE_RECOGNITION_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    finalize_warning = (
                        "終了時fallbackブキ表示判定がタイムアウトしました",
                        (
                            "終了時fallbackブキ表示判定タイムアウト"
                            f" timeout_seconds={FINALIZE_RECOGNITION_TIMEOUT_SECONDS}"
                        ),
                    )
                    break
                except Exception as exc:
                    finalize_warning = (
                        "終了時fallbackブキ表示判定に失敗しました",
                        str(exc),
                    )
                    continue

                self._logger.info(
                    "終了時fallbackブキ表示判定完了",
                    fallback_frame_index=fallback_frame_index,
                    fallback_frame_count=fallback_frame_count,
                    frame_elapsed_seconds=queued_frame.elapsed_seconds,
                    display_visible=is_visible,
                )
                if not is_visible:
                    continue

                try:
                    self._logger.info(
                        "終了時fallbackブキ判別開始",
                        fallback_frame_index=fallback_frame_index,
                        fallback_frame_count=fallback_frame_count,
                        frame_elapsed_seconds=queued_frame.elapsed_seconds,
                        target_slot_count=len(target_slots),
                        target_slots=sorted(target_slots),
                    )
                    final_result = await asyncio.wait_for(
                        self._run_recognizer_call(
                            lambda: self._recognizer.recognize_weapons(
                                queued_frame.frame,
                                save_predict_weapons_output=False,
                                target_slots=target_slots,
                                previous_results=previous_results,
                                battle_dir_name=None,
                            )
                        ),
                        timeout=FINALIZE_RECOGNITION_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    finalize_warning = (
                        "終了時fallbackブキ判別がタイムアウトしました",
                        (
                            "終了時fallbackブキ判別タイムアウト"
                            f" timeout_seconds={FINALIZE_RECOGNITION_TIMEOUT_SECONDS}"
                        ),
                    )
                    break
                except Exception as exc:
                    finalize_warning = (
                        "終了時fallbackブキ判別に失敗しました",
                        str(exc),
                    )
                    continue

                matched_slot_count = 0
                for slot_result in final_result.slot_results:
                    index = SLOT_NAMES.index(slot_result.slot)
                    best_scores[index] = max(
                        best_scores[index], slot_result.best_score
                    )
                    previous_results[slot_result.slot] = slot_result
                    if not slot_result.is_unmatched:
                        labels[index] = slot_result.predicted_weapon
                        if slot_result.slot in target_slots:
                            matched_slot_count += 1
                remaining_unknown_slots = _get_unknown_slot_names(labels)
                self._logger.info(
                    "終了時fallbackブキ判別完了",
                    fallback_frame_index=fallback_frame_index,
                    fallback_frame_count=fallback_frame_count,
                    matched_slot_count=matched_slot_count,
                    remaining_unknown_slot_count=len(remaining_unknown_slots),
                )
                if should_save_report:
                    report_frame = queued_frame.frame.copy()
                    report_slot_results = final_result.slot_results

        if (
            not candidate_frames
            and _has_unknown_slots(labels)
            and report_frame is None
            and not self._predict_weapons_output_attempted
        ):
            if (
                diagnostic_frame is not None
                and not self._predict_weapons_output_attempted
            ):
                frame_for_output = diagnostic_frame.copy()
                diagnostic_visible = False
                try:
                    diagnostic_visible = await asyncio.wait_for(
                        self._run_recognizer_call(
                            lambda: self._recognizer.detect_weapon_display(
                                frame_for_output
                            )
                        ),
                        timeout=FINALIZE_RECOGNITION_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    finalize_warning = (
                        "終了時診断フレームのブキ表示判定がタイムアウトしました",
                        (
                            "ブキ表示判定タイムアウト"
                            f" timeout_seconds={FINALIZE_RECOGNITION_TIMEOUT_SECONDS}"
                        ),
                    )
                except Exception as exc:
                    finalize_warning = (
                        "終了時診断フレームのブキ表示判定に失敗しました",
                        str(exc),
                    )

                if diagnostic_visible:
                    previous_results = _build_previous_results(context)
                    target_slots = _get_unknown_slot_names(labels)
                    try:
                        final_result = await asyncio.wait_for(
                            self._run_recognizer_call(
                                lambda: self._recognizer.recognize_weapons(
                                    frame_for_output,
                                    save_predict_weapons_output=False,
                                    target_slots=target_slots,
                                    previous_results=previous_results,
                                    battle_dir_name=None,
                                )
                            ),
                            timeout=FINALIZE_RECOGNITION_TIMEOUT_SECONDS,
                        )
                        for slot_result in final_result.slot_results:
                            index = SLOT_NAMES.index(slot_result.slot)
                            best_scores[index] = max(
                                best_scores[index], slot_result.best_score
                            )
                            previous_results[slot_result.slot] = slot_result
                            if not slot_result.is_unmatched:
                                labels[index] = slot_result.predicted_weapon
                        report_frame = frame_for_output
                        report_slot_results = final_result.slot_results
                        saved_predict_weapons_output_from_diagnostic_frame = (
                            True
                        )
                    except asyncio.TimeoutError:
                        finalize_warning = (
                            "終了時診断フレームのブキ判別がタイムアウトしました",
                            (
                                "ブキ判別タイムアウト"
                                f" timeout_seconds={FINALIZE_RECOGNITION_TIMEOUT_SECONDS}"
                            ),
                        )
                    except Exception as exc:
                        finalize_warning = (
                            "終了時診断フレームのブキ判別に失敗しました",
                            str(exc),
                        )
                else:
                    diagnostic_slot_results_by_slot = _build_previous_results(
                        context
                    )
                    diagnostic_slot_results = tuple(
                        diagnostic_slot_results_by_slot[slot]
                        for slot in SLOT_NAMES
                    )
                    report_frame = frame_for_output
                    report_slot_results = diagnostic_slot_results
                    saved_predict_weapons_output_from_diagnostic_frame = True
            else:
                skipped_predict_weapons_output_no_visible_frame = True

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
            skipped_predict_weapons_output_no_visible_frame=(
                skipped_predict_weapons_output_no_visible_frame
            ),
            saved_predict_weapons_output_from_diagnostic_frame=(
                saved_predict_weapons_output_from_diagnostic_frame
            ),
            report_frame=report_frame,
            report_slot_results=report_slot_results,
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
            score_improved = current_best > previous_best + 1e-12
            previous_label_is_unknown = _is_unknown_weapon_label(
                current_labels[index]
            )
            current_label_is_known = _is_known_slot_result(slot_result)
            should_replace_slot = score_improved
            if previous_label_is_unknown and current_label_is_known:
                should_replace_slot = True
            if not previous_label_is_unknown and not current_label_is_known:
                should_replace_slot = False
            if not should_replace_slot:
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

        # weapon_slot_resultsをタプルに変換（SLOT_NAMESの順序で）
        updated_slot_results = tuple(
            slot_results_by_slot.get(
                slot,
                WeaponSlotResult(
                    slot=slot,
                    predicted_weapon=current_labels[i],
                    is_unmatched=_is_unknown_weapon_label(current_labels[i]),
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
        )

        if done:
            if result.visible_frame is not None:
                self._start_report_output_task(
                    frame=result.visible_frame,
                    context=updated_context,
                    slot_results=recognition_result.slot_results,
                )
            self._publish_updates(
                metadata=updated_metadata,
                allies=allies,
                enemies=enemies,
                elapsed_seconds=result.elapsed_seconds,
                attempts=attempts,
                is_final=done,
            )
        if done:
            self._logger.info(
                "ブキ判別ウィンドウ内で全スロット判明",
                display_check_count=self._display_check_count,
                visible_hit_count=self._visible_hit_count,
                elapsed_seconds=result.elapsed_seconds,
                attempts=attempts,
            )
            self._reset_frame_buffers()
            self._reset_detection_statistics()
            self._window_closed = True
            self._finalize_started = True
        return updated_context

    def _start_report_output_task(
        self,
        *,
        frame: Frame,
        context: RecordingContext,
        slot_results: tuple[WeaponSlotResult, ...],
    ) -> None:
        if self._predict_weapons_output_attempted:
            return
        self._cleanup_report_output_task()
        if self._report_output_task is not None:
            return
        self._predict_weapons_output_attempted = True
        battle_dir_name = _build_battle_dir_name(context)
        self._report_output_task = asyncio.create_task(
            self._run_report_output_task(
                frame=frame.copy(),
                slot_results=slot_results,
                battle_dir_name=battle_dir_name,
            )
        )

    async def _run_report_output_task(
        self,
        *,
        frame: Frame,
        slot_results: tuple[WeaponSlotResult, ...],
        battle_dir_name: str | None,
    ) -> None:
        try:
            predict_weapons_output_dir = await self._run_recognizer_call(
                lambda: self._recognizer.save_predict_weapons_output(
                    frame,
                    slot_results=slot_results,
                    battle_dir_name=battle_dir_name,
                )
            )
            _ = predict_weapons_output_dir
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self._logger.warning(
                "predict_weapons 出力の保存がタイムアウトしました",
                error=(
                    "ブキ判別タイムアウト"
                    f" timeout_seconds={FINALIZE_RECOGNITION_TIMEOUT_SECONDS}"
                ),
            )
        except Exception as exc:
            self._logger.warning(
                "predict_weapons 出力の保存に失敗しました",
                error=str(exc),
            )

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
            weapon_slot_results=(
                result.report_slot_results
                if result.report_slot_results is not None
                else context.weapon_slot_results
            ),
            weapon_detection_done=True,
        )
        if (
            result.report_frame is not None
            and result.report_slot_results is not None
        ):
            self._start_report_output_task(
                frame=result.report_frame,
                context=updated_context,
                slot_results=result.report_slot_results,
            )
        self._reset_frame_buffers()
        self._reset_detection_statistics()
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
            RecordingMetadataUpdated(
                metadata=recording_metadata_to_dict(metadata)
            )
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
    return any(_is_unknown_weapon_label(label) for label in labels)


def _mark_detection_done_if_all_slots_known(
    context: RecordingContext,
) -> RecordingContext:
    if context.weapon_detection_done:
        return context
    if _has_unknown_slots(_normalize_weapon_labels(context.metadata)):
        return context
    return replace(context, weapon_detection_done=True)


def _is_unknown_weapon_label(label: str) -> bool:
    return (not label) or label == UNKNOWN_WEAPON_LABEL


def _is_known_slot_result(slot_result: WeaponSlotResult) -> bool:
    return not slot_result.is_unmatched and not _is_unknown_weapon_label(
        slot_result.predicted_weapon
    )


def _is_result_complete(result: WeaponRecognitionResult) -> bool:
    """WeaponRecognitionResultが全スロット判別完了かどうかを返す。"""
    return all(
        not slot_result.is_unmatched for slot_result in result.slot_results
    )


def _display_details_log_fields(
    details: WeaponDisplayDetectionResult | None,
) -> dict[str, object]:
    if details is None:
        return {}
    fields: dict[str, object] = {
        "display_reason": details.reason,
        "display_score": details.score,
        "ally_reliable_slot_count": details.ally_reliable_slot_count,
        "enemy_reliable_slot_count": details.enemy_reliable_slot_count,
        "outline_matched_slots": details.outline_matched_slots,
        "outline_matched_ally_slots": details.outline_matched_ally_slots,
        "outline_matched_enemy_slots": details.outline_matched_enemy_slots,
    }
    optional_field_names = (
        "outline_team_slots_reliable",
        "display_weapon_region_ratio",
        "display_weapon_region_ratio_passed",
        "matched_slot_team_edge_ratio",
        "matched_slot_team_edge_ratio_passed",
        "matched_slot_weapon_region_gray_std",
        "matched_slot_weapon_region_gray_std_passed",
        "fallback_used",
    )
    for field_name in optional_field_names:
        value = getattr(details, field_name, None)
        if value is not None:
            fields[field_name] = value
    return fields


def _get_unknown_slot_names(labels: list[str]) -> set[str]:
    """未判明のスロット名のセットを返す。"""
    unknown_slots = set()
    for index, label in enumerate(labels):
        if _is_unknown_weapon_label(label):
            unknown_slots.add(SLOT_NAMES[index])
    return unknown_slots


def _build_slot_results_from_labels(
    labels: list[str],
    best_scores: list[float],
) -> dict[str, WeaponSlotResult]:
    results: dict[str, WeaponSlotResult] = {}
    for index, slot in enumerate(SLOT_NAMES):
        label = labels[index]
        score = best_scores[index]
        if label and label != UNKNOWN_WEAPON_LABEL:
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
                detected_score=score if score >= 0.0 else None,
            )
        else:
            results[slot] = WeaponSlotResult(
                slot=slot,
                predicted_weapon=UNKNOWN_WEAPON_LABEL,
                is_unmatched=True,
                top_candidates=(),
            )
    return results


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
                detected_score=score if score >= 0.0 else None,
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


def _build_battle_dir_name(context: RecordingContext) -> str | None:
    if context.metadata.started_at is not None:
        return context.metadata.started_at.strftime("%Y%m%d_%H%M%S")
    if context.battle_started_at > 0.0:
        return datetime.fromtimestamp(context.battle_started_at).strftime(
            "%Y%m%d_%H%M%S"
        )
    return None
