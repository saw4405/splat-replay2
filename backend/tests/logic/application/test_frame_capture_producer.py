from __future__ import annotations

import queue
import threading

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
