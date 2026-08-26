from __future__ import annotations

import queue
import threading
from collections.abc import Callable

import numpy as np

from splat_replay.application.services.recording.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.domain.models import Frame, as_frame


class _QueuedCapture:
    def __init__(self) -> None:
        self.frames: queue.Queue[Frame] = queue.Queue()

    def setup(self) -> None:
        return None

    def capture(self) -> Frame | None:
        try:
            return self.frames.get_nowait()
        except queue.Empty:
            return None

    def current_time_seconds(self) -> float | None:
        return None

    def teardown(self) -> None:
        return None


class _BlockingFirstCapture:
    def __init__(self, first_frame: Frame) -> None:
        self.first_frame = first_frame
        self.frames: queue.Queue[Frame] = queue.Queue()
        self.started = threading.Event()
        self.release = threading.Event()
        self._calls = 0
        self._lock = threading.Lock()

    def setup(self) -> None:
        return None

    def capture(self) -> Frame | None:
        with self._lock:
            self._calls += 1
            call = self._calls
        if call == 1:
            self.started.set()
            self.release.wait(timeout=5.0)
            return self.first_frame
        try:
            return self.frames.get_nowait()
        except queue.Empty:
            return None

    def current_time_seconds(self) -> float | None:
        return None

    def teardown(self) -> None:
        return None


def _frame(value: int) -> Frame:
    return as_frame(np.full((2, 2, 3), value, dtype=np.uint8))


class _EventFramePublisher:
    """フレームパブリッシュ時にイベントをシグナルするテスト用パブリッシャー"""

    def __init__(self, event: threading.Event) -> None:
        self.event = event

    def publish_frame(self, frame: Frame) -> None:
        self.event.set()


class _FakeClock:
    def __init__(self) -> None:
        self._now = 0.0

    def monotonic(self) -> float:
        return self._now

    def wait(self, timeout: float) -> bool:
        self._now += timeout
        return False


class _TimedCapture:
    def __init__(self, monotonic: Callable[[], float]) -> None:
        self._monotonic = monotonic
        self.capture_started_at: list[float] = []
        self.on_capture: Callable[[int], None] | None = None

    def setup(self) -> None:
        return None

    def capture(self) -> Frame | None:
        self.capture_started_at.append(self._monotonic())
        if self.on_capture is not None:
            self.on_capture(len(self.capture_started_at))
        return _frame(len(self.capture_started_at))

    def current_time_seconds(self) -> float | None:
        return None

    def teardown(self) -> None:
        return None


def test_start_discards_stale_frame_from_previous_run() -> None:
    capture = _QueuedCapture()
    publish_event = threading.Event()
    publisher = _EventFramePublisher(publish_event)
    producer = FrameCaptureProducer(
        capture,
        frame_publisher=publisher,
        queue_maxsize=1,
        device_retry_sleep=0.01,
    )
    old_frame = _frame(1)
    new_frame = _frame(2)

    capture.frames.put(old_frame)
    producer.start()

    # ポーリングの代わりに Event の発火を待機（タイムアウト1秒）
    assert publish_event.wait(timeout=1.0), (
        "フレームのパブリッシュがタイムアウトしました"
    )
    producer.stop()

    capture.frames.put(new_frame)
    producer.start()
    try:
        frame = producer.get_frame(timeout=1.0)
    finally:
        producer.stop()

    assert frame is not None
    assert np.array_equal(frame, new_frame)


def test_late_frame_from_stopped_thread_is_discarded_after_restart() -> None:
    old_frame = _frame(1)
    new_frame = _frame(2)
    capture = _BlockingFirstCapture(old_frame)
    producer = FrameCaptureProducer(
        capture,
        frame_publisher=None,
        queue_maxsize=1,
        device_retry_sleep=0.01,
    )

    producer.start()
    assert capture.started.wait(timeout=1.0)
    producer.stop()

    capture.frames.put(new_frame)
    producer.start()
    capture.release.set()
    try:
        frame = producer.get_frame(timeout=1.0)
    finally:
        producer.stop()

    assert frame is not None
    assert np.array_equal(frame, new_frame)


def test_capture_interval_throttles_waiting_and_releases_when_armed() -> None:
    clock = _FakeClock()
    capture = _TimedCapture(clock.monotonic)
    producer = FrameCaptureProducer(
        capture,
        frame_publisher=None,
        monotonic=clock.monotonic,
        schedule_wait=clock.wait,
    )
    producer.set_capture_interval(1.0)

    def update_schedule(capture_count: int) -> None:
        if capture_count == 3:
            producer.set_capture_interval(0.0)
        elif capture_count == 5:
            producer._running.clear()

    capture.on_capture = update_schedule
    producer._running.set()
    generation = producer._next_generation()

    producer._loop(generation)

    assert capture.capture_started_at[:3] == [0.0, 1.0, 2.0]
    assert capture.capture_started_at[3:] == [2.0, 2.0]


def test_capture_interval_added_during_run_delays_next_attempt() -> None:
    clock = _FakeClock()
    capture = _TimedCapture(clock.monotonic)
    producer = FrameCaptureProducer(
        capture,
        frame_publisher=None,
        monotonic=clock.monotonic,
        schedule_wait=clock.wait,
    )

    def update_schedule(capture_count: int) -> None:
        if capture_count == 1:
            producer.set_capture_interval(1.0)
        elif capture_count == 3:
            producer._running.clear()

    capture.on_capture = update_schedule
    producer._running.set()
    generation = producer._next_generation()

    producer._loop(generation)

    assert capture.capture_started_at == [0.0, 1.0, 2.0]


def test_capture_interval_rejects_negative_value() -> None:
    producer = FrameCaptureProducer(
        _QueuedCapture(),
        frame_publisher=None,
    )

    with np.testing.assert_raises(ValueError):
        producer.set_capture_interval(-0.1)
