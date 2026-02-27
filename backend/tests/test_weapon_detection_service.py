from __future__ import annotations

import asyncio
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
        unmatched_output_dir=None,
    )


def _build_full_recognition_result(
    prefix: str,
    unmatched_output_dir: str | None = None,
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
        unmatched_output_dir=unmatched_output_dir,
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
        self.warnings: list[tuple[str, dict[str, object]]] = []

    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        self.warnings.append((event, dict(kw)))

    def error(self, event: str, **kw: object) -> None:
        return None

    def exception(self, event: str, **kw: object) -> None:
        return None


class _DetectErrorRecognizer:
    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        raise RuntimeError("detect failed")

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
        raise AssertionError("recognize_weapons should not be called")


class _BlockingRecognizer:
    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.started = asyncio.Event()
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
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
        self.recognize_calls += 1
        self.started.set()
        await self.release.wait()
        return _build_partial_recognition_result("認識結果")


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
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
        self.recognize_calls += 1
        return _build_full_recognition_result("再判定")


class _PendingOverwriteRecognizer:
    def __init__(self) -> None:
        self.release_first = asyncio.Event()
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
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
        marker = int(frame[0, 0, 0])
        self.recognize_markers.append(marker)
        if len(self.recognize_markers) == 1:
            await self.release_first.wait()
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
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
        return _build_full_recognition_result("unused")


class _CompleteDetectionRecognizer:
    def __init__(self) -> None:
        self.detect_calls = 0
        self.save_flags: list[bool] = []
        self.target_slots_history: list[set[str] | None] = []

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return True

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = previous_results
        self.save_flags.append(save_unmatched_report)
        self.target_slots_history.append(
            None if target_slots is None else set(target_slots)
        )
        if save_unmatched_report:
            return _build_full_recognition_result(
                "complete",
                unmatched_output_dir="unmatched/from-detection",
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
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = previous_results
        if save_unmatched_report:
            self.finalize_calls += 1
            self.finalize_target_slots.append(
                None if target_slots is None else set(target_slots)
            )
            return _build_full_recognition_result(
                "final",
                unmatched_output_dir="unmatched/report",
            )
        return _build_full_recognition_result("normal")


class _CancelRecognizer:
    def __init__(self) -> None:
        self.detect_calls = 0
        self.recognize_calls = 0
        self.cancel_requests = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    def request_cancel(self) -> None:
        self.cancel_requests += 1
        self.release.set()

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        self.detect_calls += 1
        return self.detect_calls == 1

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
        self.recognize_calls += 1
        self.started.set()
        await self.release.wait()
        return _build_full_recognition_result("cancelled")


class _DetectionTimeoutRecognizer:
    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        return True

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
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
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        _ = target_slots
        _ = previous_results
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
) -> RecordingContext:
    updated = context
    for _ in range(loops):
        await asyncio.sleep(0)
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

    await asyncio.sleep(0)
    updated_context = await service.process(
        frame=frame, context=updated_context
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
    await asyncio.wait_for(recognizer.started.wait(), timeout=0.2)

    recognizer.release.set()
    context = await _drive_process(service, context, frame, loops=6)
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
    await asyncio.wait_for(recognizer.started.wait(), timeout=0.2)
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
    service = WeaponDetectionService(
        cast(WeaponRecognitionPort, recognizer),
        cast(LoggerPort, logger),
        cast(EventBusPort, _SpyEventBus()),
    )
    context = _new_context(1.0)
    frame_1 = _frame(1)
    frame_2 = _frame(2)

    context = await service.process(frame=frame_1, context=context)
    context = await _drive_process(service, context, frame_2, loops=8)

    assert recognizer.detect_calls >= 2
    assert recognizer.recognize_calls >= 1
    assert context.weapon_detection_attempts == 1


@pytest.mark.asyncio
async def test_pending_frame_is_overwritten_by_latest() -> None:
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
    context = await service.process(frame=frame_2, context=context)
    context = await service.process(frame=frame_3, context=context)

    recognizer.release_first.set()
    for _ in range(20):
        await asyncio.sleep(0)
        context = await service.process(frame=frame_3, context=context)
        if len(recognizer.recognize_markers) >= 2:
            break

    assert recognizer.recognize_markers[:2] == [1, 3]
    assert context.weapon_detection_attempts >= 2


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
    context = _new_context(1.0)
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=8)

    assert context.weapon_detection_done is True
    assert recognizer.save_flags[:2] == [False, True]
    # レポート出力時はtarget_slots=set()（再判別なし）
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
    context = RecordingContext(
        battle_started_at=time.time() - 25.0,
        weapon_last_visible_frame=_frame(9),
    )
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=8)
    assert context.weapon_detection_done is True
    assert context.weapon_last_visible_frame is None
    assert recognizer.finalize_calls == 1
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
    await asyncio.wait_for(recognizer.started.wait(), timeout=0.2)
    service.request_cancel()

    context = await _drive_process(service, context, frame_2, loops=6)

    assert recognizer.cancel_requests == 1
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
    context = RecordingContext(
        battle_started_at=time.time() - 25.0,
        weapon_last_visible_frame=_frame(9),
    )
    frame = _frame(1)

    context = await service.process(frame=frame, context=context)
    await asyncio.sleep(0.1)
    context = await service.process(frame=frame, context=context)
    context = await _drive_process(service, context, frame, loops=4)

    assert context.weapon_detection_done is True
    assert context.weapon_last_visible_frame is None
    assert context.metadata.allies == _to_four([UNKNOWN_WEAPON_LABEL] * 4)
    assert context.metadata.enemies == _to_four([UNKNOWN_WEAPON_LABEL] * 4)
    warning_events = [event for event, _ in logger.warnings]
    assert "最終ブキ判別レポートの保存がタイムアウトしました" in warning_events
    final_events = [
        event
        for event in event_bus.domain_events
        if isinstance(event, BattleWeaponsDetected) and event.is_final
    ]
    assert len(final_events) == 1
