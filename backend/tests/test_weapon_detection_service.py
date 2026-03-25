from __future__ import annotations

import asyncio
import datetime
import threading
import time
from typing import Mapping, Optional, Set, cast

import numpy as np
import pytest

import splat_replay.application.services.recording.weapon_detection_service as weapon_detection_service_module
from splat_replay.application.interfaces import (
    EventBusPort,
    LoggerPort,
    WeaponCandidateScore,
    WeaponRecognitionPort,
    WeaponRecognitionResult,
    WeaponSlotResult,
)
from splat_replay.application.interfaces.messaging import EventSubscription
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.weapon_detection_service import (
    UNKNOWN_WEAPON_LABEL,
    WeaponDetectionService,
)
from splat_replay.domain.events import BattleWeaponsDetected, DomainEvent
from splat_replay.domain.models import RecordingMetadata

_SLOTS = (
    "ally_1",
    "ally_2",
    "ally_3",
    "ally_4",
    "enemy_1",
    "enemy_2",
    "enemy_3",
    "enemy_4",
)


def _to_four(items: list[str]) -> tuple[str, str, str, str]:
    if len(items) != 4:
        raise AssertionError("expected 4 items")
    return (items[0], items[1], items[2], items[3])


def _frame(marker: int) -> np.ndarray:
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    frame[0, 0, 0] = marker
    return frame


async def _wait_thread_event(
    event: threading.Event,
    *,
    timeout: float,
) -> None:
    signaled = await asyncio.to_thread(event.wait, timeout)
    if not signaled:
        raise asyncio.TimeoutError("threading.Event wait timed out")


def _build_partial_recognition_result(label: str) -> WeaponRecognitionResult:
    predicted_labels = [label] + [UNKNOWN_WEAPON_LABEL] * 7
    slot_results = []
    for index, slot in enumerate(_SLOTS):
        predicted_weapon = predicted_labels[index]
        is_unmatched = index != 0
        score = 0.9 if index == 0 else 0.1
        slot_results.append(
            WeaponSlotResult(
                slot=slot,
                predicted_weapon=predicted_weapon,
                is_unmatched=is_unmatched,
                top_candidates=(
                    WeaponCandidateScore(
                        weapon=predicted_weapon,
                        score=score,
                        threshold=0.85,
                    ),
                ),
            )
        )
    return WeaponRecognitionResult(
        allies=_to_four(predicted_labels[:4]),
        enemies=_to_four(predicted_labels[4:]),
        slot_results=tuple(slot_results),
        predict_weapons_output_dir=None,
    )


def _build_full_recognition_result(
    prefix: str,
    predict_weapons_output_dir: str | None = None,
) -> WeaponRecognitionResult:
    predicted_labels = [f"{prefix}_{index}" for index in range(8)]
    slot_results = tuple(
        WeaponSlotResult(
            slot=slot,
            predicted_weapon=predicted_labels[index],
            is_unmatched=False,
            top_candidates=(
                WeaponCandidateScore(
                    weapon=predicted_labels[index],
                    score=0.9,
                    threshold=0.85,
                ),
            ),
        )
        for index, slot in enumerate(_SLOTS)
    )
    return WeaponRecognitionResult(
        allies=_to_four(predicted_labels[:4]),
        enemies=_to_four(predicted_labels[4:]),
        slot_results=slot_results,
        predict_weapons_output_dir=predict_weapons_output_dir,
    )


def _build_slot_recognition_result(
    predicted_by_slot: Mapping[str, str],
) -> WeaponRecognitionResult:
    predicted_labels = [UNKNOWN_WEAPON_LABEL] * len(_SLOTS)
    slot_results: list[WeaponSlotResult] = []
    for index, slot in enumerate(_SLOTS):
        predicted_weapon = predicted_by_slot.get(slot, UNKNOWN_WEAPON_LABEL)
        is_unmatched = slot not in predicted_by_slot
        score = 0.9 if not is_unmatched else 0.1
        predicted_labels[index] = predicted_weapon
        slot_results.append(
            WeaponSlotResult(
                slot=slot,
                predicted_weapon=predicted_weapon,
                is_unmatched=is_unmatched,
                top_candidates=(
                    WeaponCandidateScore(
                        weapon=predicted_weapon,
                        score=score,
                        threshold=0.85,
                    ),
                ),
            )
        )
    return WeaponRecognitionResult(
        allies=_to_four(predicted_labels[:4]),
        enemies=_to_four(predicted_labels[4:]),
        slot_results=tuple(slot_results),
        predict_weapons_output_dir=None,
    )


class _DummySubscription:
    def poll(self, max_items: int = 100) -> list[object]:
        return []

    def close(self) -> None:
        return None


class _SpyEventBus:
    def __init__(self) -> None:
        self.domain_events: list[DomainEvent] = []

    def publish(
        self, event_type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        return None

    def publish_domain_event(self, event: DomainEvent) -> None:
        self.domain_events.append(event)

    def subscribe(
        self, event_types: Optional[Set[str]] = None
    ) -> EventSubscription:
        return _DummySubscription()


class _SpyLogger:
    def __init__(self) -> None:
        self.infos: list[tuple[str, dict[str, object]]] = []
        self.warnings: list[tuple[str, dict[str, object]]] = []

    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        self.infos.append((event, dict(kw)))

    def warning(self, event: str, **kw: object) -> None:
        self.warnings.append((event, dict(kw)))

    def error(self, event: str, **kw: object) -> None:
        return None

    def exception(self, event: str, **kw: object) -> None:
        return None


class _FixedClock:
    def __init__(self, now: float) -> None:
        self._now = now

    def now(self) -> float:
        return self._now


class _MutableClock:
    def __init__(self, now: float) -> None:
        self._now = now

    def now(self) -> float:
        return self._now

    def set(self, now: float) -> None:
        self._now = now


class _DetectErrorRecognizer:
    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        raise RuntimeError("detect failed")

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        raise AssertionError("recognize_weapons should not be called")


class _BlockingRecognizer:
    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = threading.Event()
        self.detect_calls = 0
        self.recognize_calls = 0

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return True

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        self.recognize_calls += 1
        self.started.set()
        self.release.wait()
        return _build_partial_recognition_result("認識結果")


class _CpuBoundRecognizeRecognizer:
    def __init__(self, *, block_seconds: float = 0.15) -> None:
        self.block_seconds = block_seconds
        self.detect_calls = 0
        self.recognize_calls = 0

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return True

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = frame
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        self.recognize_calls += 1
        time.sleep(self.block_seconds)
        return _build_partial_recognition_result("cpu-bound")


class _DisplaySequenceRecognizer:
    def __init__(self, detect_sequence: list[bool]) -> None:
        self._detect_sequence = detect_sequence
        self.detect_calls = 0
        self.recognize_calls = 0

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        index = min(self.detect_calls - 1, len(self._detect_sequence) - 1)
        return self._detect_sequence[index]

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        self.recognize_calls += 1
        return _build_full_recognition_result("再判定")


class _PendingOverwriteRecognizer:
    def __init__(self) -> None:
        self.release_first = threading.Event()
        self.started = threading.Event()
        self.detect_calls = 0
        self.recognize_markers: list[int] = []

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return True

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        marker = int(frame[0, 0, 0])
        self.recognize_markers.append(marker)
        if len(self.recognize_markers) == 1:
            self.started.set()
            self.release_first.wait()
        return _build_partial_recognition_result(f"marker_{marker}")


class _WindowClosedRecognizer:
    def __init__(self) -> None:
        self.detect_calls = 0

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return True

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        return _build_full_recognition_result("unused")


class _CompleteDetectionRecognizer:
    def __init__(self) -> None:
        self.detect_calls = 0
        self.save_flags: list[bool] = []
        self.battle_dir_names: list[str | None] = []
        self.target_slots_history: list[set[str] | None] = []

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return True

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = previous_results
        _ = frame
        self.save_flags.append(save_predict_weapons_output)
        self.battle_dir_names.append(battle_dir_name)
        self.target_slots_history.append(
            None if target_slots is None else set(target_slots)
        )
        if save_predict_weapons_output:
            return _build_full_recognition_result(
                "complete",
                predict_weapons_output_dir="predict_weapons/from-detection",
            )
        return _build_full_recognition_result("complete")


class _FinalizeRecognizer:
    def __init__(self) -> None:
        self.detect_calls = 0
        self.finalize_calls = 0
        self.finalize_target_slots: list[set[str] | None] = []

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return False

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = previous_results
        _ = frame
        _ = battle_dir_name
        if save_predict_weapons_output:
            self.finalize_calls += 1
            self.finalize_target_slots.append(
                None if target_slots is None else set(target_slots)
            )
            return _build_full_recognition_result(
                "final",
                predict_weapons_output_dir="predict_weapons/report",
            )
        return _build_full_recognition_result("normal")


class _FinalizeFromFallbackRecognizer:
    def __init__(self) -> None:
        self.detect_calls = 0
        self.finalize_calls = 0
        self.finalize_markers: list[int] = []

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return False

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        if save_predict_weapons_output:
            self.finalize_calls += 1
            self.finalize_markers.append(int(frame[0, 0, 0]))
        return _build_full_recognition_result("fallback-final")


class _SampledFrameRecognizer:
    def __init__(self, detect_by_marker: Mapping[int, bool]) -> None:
        self.detect_by_marker = dict(detect_by_marker)
        self.detect_markers: list[int] = []
        self.recognize_markers: list[int] = []

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        marker = int(frame[0, 0, 0])
        self.detect_markers.append(marker)
        return self.detect_by_marker.get(marker, True)

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        marker = int(frame[0, 0, 0])
        self.recognize_markers.append(marker)
        return _build_partial_recognition_result(f"marker_{marker}")


class _FinalizeCandidatesRecognizer:
    def __init__(
        self,
        *,
        result_by_marker: Mapping[int, WeaponRecognitionResult] | None = None,
        fail_markers: set[int] | None = None,
    ) -> None:
        self.result_by_marker = dict(result_by_marker or {})
        self.fail_markers = set(fail_markers or set())
        self.finalize_markers: list[int] = []

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        return False

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        marker = int(frame[0, 0, 0])
        self.finalize_markers.append(marker)
        if marker in self.fail_markers:
            raise RuntimeError(f"candidate failed: {marker}")
        return self.result_by_marker.get(
            marker,
            _build_full_recognition_result(f"candidate_{marker}"),
        )


class _CancelRecognizer:
    def __init__(self) -> None:
        self.detect_calls = 0
        self.recognize_calls = 0
        self.cancel_requests = 0
        self.started = threading.Event()
        self.release = threading.Event()

    def request_cancel(self) -> None:
        self.cancel_requests += 1
        self.release.set()

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return self.detect_calls == 1

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        self.recognize_calls += 1
        self.started.set()
        self.release.wait()
        return _build_full_recognition_result("cancelled")


class _DetectionTimeoutRecognizer:
    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        return True

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        await asyncio.sleep(0.05)
        return _build_partial_recognition_result("timeout")


class _FinalizeTimeoutRecognizer:
    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        return False

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
        await asyncio.sleep(0.05)
        return _build_full_recognition_result("final-timeout")


def _new_context(seconds_ago: float) -> RecordingContext:
    return RecordingContext(battle_started_at=time.time() - seconds_ago)


async def _drive_process(
    service: WeaponDetectionService,
    context: RecordingContext,
    frame: np.ndarray,
    *,
    loops: int,
    delay_seconds: float = 0.01,
) -> RecordingContext:
    updated = context
    for _ in range(loops):
        await asyncio.sleep(delay_seconds)
        updated = await service.process(frame=frame, context=updated)
    return updated


@pytest.mark.asyncio
async def test_process_continues_when_detect_weapon_display_raises() -> None:
    logger = _SpyLogger()
    event_bus = _SpyEventBus()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, _DetectErrorRecognizer()),
        cast(LoggerPort, logger),
        cast(EventBusPort, event_bus),
    )
    context = _new_context(1.0)
    frame = _frame(1)

    updated_context = await service.process(frame=frame, context=context)
    assert updated_context == context

    updated_context = await _drive_process(
        service,
        updated_context,
        frame,
        loops=4,
    )

    assert updated_context == context
    assert len(logger.warnings) >= 1
    warning_event, warning_fields = logger.warnings[0]
    assert warning_event == "ブキ表示判定に失敗しました"
    assert warning_fields["error"] == "detect failed"


@pytest.mark.asyncio
async def test_process_is_non_blocking_when_recognition_inflight() -> None:
    recognizer = _BlockingRecognizer()
    logger = _SpyLogger()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, logger),
        cast(EventBusPort, _SpyEventBus()),
    )
    context = _new_context(1.0)
    frame = _frame(1)

    context = await asyncio.wait_for(
        service.process(frame=frame, context=context), timeout=0.1
    )
    context = await asyncio.wait_for(
        service.process(frame=frame, context=context), timeout=0.1
    )
    assert context.weapon_detection_attempts == 0
    await _wait_thread_event(recognizer.started, timeout=1.0)

    recognizer.release.set()
    for _ in range(20):
        await asyncio.sleep(0.01)
        context = await service._drain_completed_task(context)
        if context.weapon_detection_attempts >= 1:
            break
    assert context.weapon_detection_attempts >= 1
    service.request_cancel()


@pytest.mark.asyncio
async def test_process_keeps_event_loop_responsive_when_recognition_is_cpu_bound() -> (
    None
):
    recognizer = _CpuBoundRecognizeRecognizer()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, _SpyEventBus()),
    )
    context = _new_context(1.0)
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)

    start = time.perf_counter()
    await asyncio.sleep(0)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.05

    await asyncio.sleep(recognizer.block_seconds + 0.05)
    context = await _drive_process(service, context, frame, loops=4)
    assert context.weapon_detection_attempts >= 1


@pytest.mark.asyncio
async def test_partial_detection_does_not_publish_final_event() -> None:
    recognizer = _BlockingRecognizer()
    event_bus = _SpyEventBus()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, event_bus),
    )
    context = _new_context(1.0)
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    await _wait_thread_event(recognizer.started, timeout=0.2)
    recognizer.release.set()
    context = await _drive_process(service, context, frame, loops=8)

    assert context.weapon_detection_done is False
    final_events = [
        event
        for event in event_bus.domain_events
        if isinstance(event, BattleWeaponsDetected) and event.is_final
    ]
    assert final_events == []


@pytest.mark.asyncio
async def test_display_ng_finishes_task_and_next_frame_retries_detection() -> (
    None
):
    recognizer = _DisplaySequenceRecognizer([False, True])
    logger = _SpyLogger()
    clock = _MutableClock(100.0)
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, logger),
        cast(EventBusPort, _SpyEventBus()),
        clock=clock,
    )
    context = RecordingContext(battle_started_at=100.0)
    frame_1 = _frame(1)
    frame_2 = _frame(2)

    context = await service.process(frame=frame_1, context=context)
    await asyncio.sleep(0.05)

    clock.set(100.05)
    context = await service.process(frame=frame_2, context=context)
    assert recognizer.detect_calls == 1

    clock.set(
        100.0
        + weapon_detection_service_module.DISPLAY_CHECK_INTERVAL_SECONDS
        + 0.01
    )
    context = await service.process(frame=frame_2, context=context)
    await asyncio.sleep(0.05)
    clock.set(
        100.0
        + weapon_detection_service_module.DISPLAY_CHECK_INTERVAL_SECONDS
        + 0.02
    )
    context = await service.process(frame=frame_2, context=context)

    assert recognizer.detect_calls >= 2
    assert recognizer.recognize_calls >= 1
    assert context.weapon_detection_attempts == 1


@pytest.mark.asyncio
async def test_display_checks_are_throttled_before_visible_detection() -> None:
    recognizer = _DisplaySequenceRecognizer([False, False, False, False])
    clock = _MutableClock(100.0)
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, _SpyEventBus()),
        clock=clock,
    )
    context = RecordingContext(battle_started_at=100.0)
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    await asyncio.sleep(0.05)

    for offset in (0.05, 0.10, 0.15, 0.20):
        clock.set(100.0 + offset)
        context = await service.process(frame=frame, context=context)
        await asyncio.sleep(0.05)

    assert recognizer.detect_calls == 1
    assert context.weapon_detection_attempts == 0

    clock.set(
        100.0
        + weapon_detection_service_module.DISPLAY_CHECK_INTERVAL_SECONDS
        + 0.01
    )
    context = await service.process(frame=frame, context=context)
    await asyncio.sleep(0.05)
    clock.set(
        100.0
        + weapon_detection_service_module.DISPLAY_CHECK_INTERVAL_SECONDS
        + 0.02
    )
    context = await service.process(frame=frame, context=context)

    assert recognizer.detect_calls == 2
    assert context.weapon_detection_attempts == 0


@pytest.mark.asyncio
async def test_pending_frame_keeps_latest_after_sampled_frame() -> None:
    recognizer = _PendingOverwriteRecognizer()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, _SpyEventBus()),
    )
    context = _new_context(1.0)
    frame_1 = _frame(1)
    frame_2 = _frame(2)
    frame_3 = _frame(3)

    context = await service.process(frame=frame_1, context=context)
    await _wait_thread_event(recognizer.started, timeout=0.2)
    context = await service.process(frame=frame_2, context=context)
    context = await service.process(frame=frame_3, context=context)

    recognizer.release_first.set()
    # DISPLAY_CHECK_INTERVAL_SECONDS=0.25 が2回（frame_2, frame_3）必要なため
    # 合計 0.5 秒以上のループ時間を確保する（100回×0.01秒=1.0秒）
    for _ in range(100):
        await asyncio.sleep(0.01)
        context = await service.process(frame=frame_3, context=context)
        if len(recognizer.recognize_markers) >= 3:
            break

    assert recognizer.recognize_markers[:3] == [1, 2, 3]
    assert context.weapon_detection_attempts >= 3


@pytest.mark.asyncio
async def test_no_new_submission_after_detection_window_closed() -> None:
    recognizer = _WindowClosedRecognizer()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, _SpyEventBus()),
    )
    context = _new_context(25.0)
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=8)

    assert recognizer.detect_calls == 0
    assert context.weapon_detection_done is True


@pytest.mark.asyncio
async def test_detection_completion_saves_report_once() -> None:
    recognizer = _CompleteDetectionRecognizer()
    event_bus = _SpyEventBus()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, event_bus),
    )
    context = RecordingContext(
        battle_started_at=time.time() - 1.0,
        metadata=RecordingMetadata(
            started_at=datetime.datetime(2026, 3, 22, 12, 34, 56)
        ),
    )
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=8)

    assert context.weapon_detection_done is True
    assert recognizer.save_flags[:2] == [False, True]
    assert recognizer.battle_dir_names[:2] == [None, "20260322_123456"]
    # predict_weapons 出力時は target_slots=set()（再判別なし）
    assert recognizer.target_slots_history[1] == set()

    context = await _drive_process(service, context, frame, loops=4)
    assert recognizer.save_flags[:2] == [False, True]
    assert len(recognizer.save_flags) == 2

    final_events = [
        event
        for event in event_bus.domain_events
        if isinstance(event, BattleWeaponsDetected) and event.is_final
    ]
    assert len(final_events) == 1


@pytest.mark.asyncio
async def test_finalize_runs_once_after_window_and_marks_done() -> None:
    recognizer = _FinalizeRecognizer()
    event_bus = _SpyEventBus()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, event_bus),
    )
    battle_started_at = time.time() - 25.0
    context = RecordingContext(battle_started_at=battle_started_at)
    service._active_battle_started_at = battle_started_at
    service._visible_candidates.append(_frame(9))
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=8)
    assert context.weapon_detection_done is True
    assert recognizer.finalize_calls == 1
    assert list(service._visible_candidates) == []
    assert list(service._sampled_frames) == []
    # 全スロット未判別のため、target_slotsは全スロットのセット
    assert len(recognizer.finalize_target_slots) == 1
    assert recognizer.finalize_target_slots[0] == set(_SLOTS)

    context = await _drive_process(service, context, frame, loops=4)
    assert context.weapon_detection_done is True
    assert recognizer.finalize_calls == 1

    final_events = [
        event
        for event in event_bus.domain_events
        if isinstance(event, BattleWeaponsDetected) and event.is_final
    ]
    assert len(final_events) == 1


@pytest.mark.asyncio
async def test_finalize_does_not_use_non_visible_fallback_frame() -> None:
    recognizer = _FinalizeFromFallbackRecognizer()
    event_bus = _SpyEventBus()
    clock = _MutableClock(101.0)
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, event_bus),
        clock=clock,
    )
    context = RecordingContext(battle_started_at=100.0)
    frame = _frame(7)

    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=8)
    assert recognizer.detect_calls >= 1

    clock.set(125.0)
    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=16)

    assert recognizer.finalize_calls == 0
    assert recognizer.finalize_markers == []
    assert context.weapon_detection_done is True
    assert context.metadata.allies == _to_four([UNKNOWN_WEAPON_LABEL] * 4)
    assert context.metadata.enemies == _to_four([UNKNOWN_WEAPON_LABEL] * 4)


@pytest.mark.asyncio
async def test_busy_recognition_samples_frames_at_fixed_interval() -> None:
    recognizer = _BlockingRecognizer()
    clock = _MutableClock(100.0)
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, _SpyEventBus()),
        clock=clock,
    )
    context = RecordingContext(battle_started_at=100.0)

    context = await service.process(frame=_frame(1), context=context)
    await _wait_thread_event(recognizer.started, timeout=0.2)

    clock.set(100.10)
    context = await service.process(frame=_frame(2), context=context)
    clock.set(100.20)
    context = await service.process(frame=_frame(3), context=context)
    clock.set(100.46)
    context = await service.process(frame=_frame(4), context=context)

    assert [int(item.frame[0, 0, 0]) for item in service._sampled_frames] == [
        2,
        4,
    ]

    recognizer.release.set()
    context = await _drive_process(service, context, _frame(4), loops=12)


@pytest.mark.asyncio
async def test_sampled_frames_promote_only_visible_frames() -> None:
    recognizer = _SampledFrameRecognizer(
        detect_by_marker={2: False, 3: True, 4: True}
    )
    clock = _MutableClock(100.0)
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, _SpyEventBus()),
        clock=clock,
    )
    context = RecordingContext(battle_started_at=100.0)
    service._sampled_frames.extend(
        [
            weapon_detection_service_module._QueuedFrame(
                frame=_frame(2),
                elapsed_seconds=0.1,
            ),
            weapon_detection_service_module._QueuedFrame(
                frame=_frame(3),
                elapsed_seconds=0.4,
            ),
            weapon_detection_service_module._QueuedFrame(
                frame=_frame(4),
                elapsed_seconds=0.7,
            ),
        ]
    )
    while service._sampled_frames:
        queued_frame = service._pop_next_detection_frame()
        assert queued_frame is not None
        result = await service._run_detection_task(
            frame=queued_frame.frame,
            context=context,
            generation=service._generation,
            battle_started_at=context.battle_started_at,
            elapsed_seconds=queued_frame.elapsed_seconds,
        )
        context = service._apply_task_result(context=context, result=result)

    candidate_markers = [
        int(candidate[0, 0, 0]) for candidate in service._visible_candidates
    ]
    assert recognizer.detect_markers == [2, 3, 4]
    assert recognizer.recognize_markers == [3, 4]
    assert 2 not in candidate_markers
    assert candidate_markers == [3, 4]
    assert list(service._sampled_frames) == []


@pytest.mark.asyncio
async def test_finalize_logs_display_check_counts_when_no_visible_candidate() -> (
    None
):
    recognizer = _DisplaySequenceRecognizer([False, False, False])
    logger = _SpyLogger()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, logger),
        cast(EventBusPort, _SpyEventBus()),
    )
    battle_started_at = time.time() - 25.0
    context = RecordingContext(battle_started_at=battle_started_at)

    for elapsed_seconds in (0.1, 0.4, 0.7):
        result = await service._run_detection_task(
            frame=_frame(1),
            context=context,
            generation=service._generation,
            battle_started_at=context.battle_started_at,
            elapsed_seconds=elapsed_seconds,
        )
        context = service._apply_task_result(context=context, result=result)

    finalize_result = await service._run_finalize_task(
        context=context,
        generation=service._generation,
        battle_started_at=context.battle_started_at,
        elapsed_seconds=25.0,
    )
    context = service._apply_task_result(
        context=context,
        result=finalize_result,
    )

    assert context.weapon_detection_done is True
    assert logger.infos
    info_event, info_fields = logger.infos[-1]
    assert info_event == "ブキ表示未検出のため predict_weapons 出力をスキップ"
    assert info_fields["display_check_count"] == 3
    assert info_fields["visible_hit_count"] == 0


@pytest.mark.asyncio
async def test_finalize_tries_visible_candidates_from_newest_to_oldest() -> (
    None
):
    recognizer = _FinalizeCandidatesRecognizer(
        result_by_marker={
            4: _build_slot_recognition_result({"ally_1": "candidate_4"}),
            3: _build_full_recognition_result("candidate_3"),
        }
    )
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, _SpyEventBus()),
    )
    battle_started_at = time.time() - 25.0
    context = RecordingContext(battle_started_at=battle_started_at)
    service._active_battle_started_at = battle_started_at
    service._visible_candidates.extend([_frame(1), _frame(3), _frame(4)])
    frame = _frame(9)

    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=8)

    assert recognizer.finalize_markers == [4, 3]
    assert context.weapon_detection_done is True
    assert context.metadata.allies == _to_four(
        [f"candidate_3_{index}" for index in range(4)]
    )


@pytest.mark.asyncio
async def test_finalize_continues_after_candidate_failure() -> None:
    logger = _SpyLogger()
    recognizer = _FinalizeCandidatesRecognizer(
        result_by_marker={3: _build_full_recognition_result("recovered")},
        fail_markers={4},
    )
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, logger),
        cast(EventBusPort, _SpyEventBus()),
    )
    battle_started_at = time.time() - 25.0
    context = RecordingContext(battle_started_at=battle_started_at)
    service._active_battle_started_at = battle_started_at
    service._visible_candidates.extend([_frame(3), _frame(4)])
    frame = _frame(9)

    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=8)

    assert recognizer.finalize_markers == [4, 3]
    assert context.weapon_detection_done is True
    warning_events = [event for event, _ in logger.warnings]
    assert "最終 predict_weapons 出力の保存に失敗しました" in warning_events


@pytest.mark.asyncio
async def test_request_cancel_prevents_late_apply() -> None:
    recognizer = _CancelRecognizer()
    event_bus = _SpyEventBus()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, event_bus),
    )
    context = _new_context(1.0)
    frame_1 = _frame(1)
    frame_2 = _frame(2)

    context = await service.process(frame=frame_1, context=context)
    await _wait_thread_event(recognizer.started, timeout=0.2)
    service._visible_candidates.append(_frame(9))
    service._sampled_frames.append(
        weapon_detection_service_module._QueuedFrame(
            frame=_frame(8),
            elapsed_seconds=0.2,
        )
    )
    service.request_cancel()

    context = await _drive_process(service, context, frame_2, loops=6)

    assert recognizer.cancel_requests == 1
    assert list(service._visible_candidates) == []
    assert list(service._sampled_frames) == []
    assert context.weapon_detection_attempts == 0
    battle_events = [
        event
        for event in event_bus.domain_events
        if isinstance(event, BattleWeaponsDetected)
    ]
    assert battle_events == []


@pytest.mark.asyncio
async def test_detection_timeout_continues_without_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        weapon_detection_service_module,
        "DETECTION_RECOGNITION_TIMEOUT_SECONDS",
        0.01,
    )
    logger = _SpyLogger()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, _DetectionTimeoutRecognizer()),
        cast(LoggerPort, logger),
        cast(EventBusPort, _SpyEventBus()),
    )
    context = _new_context(1.0)
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    await asyncio.sleep(0.1)
    context = await service.process(frame=frame, context=context)

    assert context.weapon_detection_attempts == 0
    assert context.weapon_detection_done is False
    warning_events = [event for event, _ in logger.warnings]
    assert "ブキ判別がタイムアウトしました" in warning_events


@pytest.mark.asyncio
async def test_finalize_timeout_marks_done_with_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        weapon_detection_service_module,
        "FINALIZE_RECOGNITION_TIMEOUT_SECONDS",
        0.01,
    )
    logger = _SpyLogger()
    event_bus = _SpyEventBus()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, _FinalizeTimeoutRecognizer()),
        cast(LoggerPort, logger),
        cast(EventBusPort, event_bus),
    )
    battle_started_at = time.time() - 25.0
    context = RecordingContext(battle_started_at=battle_started_at)
    service._active_battle_started_at = battle_started_at
    service._visible_candidates.append(_frame(9))
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    await asyncio.sleep(0.1)
    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=4)

    assert context.weapon_detection_done is True
    assert context.metadata.allies == _to_four([UNKNOWN_WEAPON_LABEL] * 4)
    assert context.metadata.enemies == _to_four([UNKNOWN_WEAPON_LABEL] * 4)
    warning_events = [event for event, _ in logger.warnings]
    assert (
        "最終 predict_weapons 出力の保存がタイムアウトしました"
        in warning_events
    )
    final_events = [
        event
        for event in event_bus.domain_events
        if isinstance(event, BattleWeaponsDetected) and event.is_final
    ]
    assert len(final_events) == 1


@pytest.mark.asyncio
async def test_detection_window_uses_injected_clock() -> None:
    recognizer = _WindowClosedRecognizer()
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, _SpyLogger()),
        cast(EventBusPort, _SpyEventBus()),
        clock=_FixedClock(125.0),
    )
    context = RecordingContext(battle_started_at=100.0)
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=8)

    assert recognizer.detect_calls == 0
    assert context.weapon_detection_done is True
