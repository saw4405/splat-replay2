"""電源ON待機中の実キャプチャ頻度を実時間で検証する。"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from splat_replay.application.services.recording.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.application.use_cases.auto_recording_use_case import (
    POWER_ON_WAIT_CAPTURE_INTERVAL_SECONDS,
)
from splat_replay.domain.models import Frame, as_frame

pytestmark = pytest.mark.perf


class _CaptureStartRecorder:
    def __init__(self) -> None:
        self._frame = as_frame(np.zeros((2, 2, 3), dtype=np.uint8))
        self._lock = threading.Lock()
        self._first_capture = threading.Event()
        self._three_captures = threading.Event()
        self.capture_started_at: list[float] = []

    def setup(self) -> None:
        return None

    def capture(self) -> Frame | None:
        with self._lock:
            self.capture_started_at.append(time.perf_counter())
            self._first_capture.set()
            if len(self.capture_started_at) >= 3:
                self._three_captures.set()
        return self._frame

    def current_time_seconds(self) -> float | None:
        return None

    def teardown(self) -> None:
        return None

    def wait_for_three_captures(self, timeout: float) -> bool:
        return self._three_captures.wait(timeout)

    def wait_for_first_capture(self, timeout: float) -> bool:
        return self._first_capture.wait(timeout)


def test_power_on_wait_capture_starts_at_most_once_per_second() -> None:
    capture = _CaptureStartRecorder()
    producer = FrameCaptureProducer(capture, frame_publisher=None)
    producer.set_capture_interval(POWER_ON_WAIT_CAPTURE_INTERVAL_SECONDS)

    producer.start()
    try:
        assert capture.wait_for_three_captures(timeout=3.5)
    finally:
        producer.stop()

    first_three = capture.capture_started_at[:3]
    gaps = [
        later - earlier for earlier, later in zip(first_three, first_three[1:])
    ]

    # Windowsのタイマー精度を50ms許容しつつ、約1Hzより速い回帰を検出する。
    assert min(gaps) >= 0.95


def test_stop_interrupts_long_capture_wait() -> None:
    capture = _CaptureStartRecorder()
    producer = FrameCaptureProducer(capture, frame_publisher=None)
    producer.set_capture_interval(60.0)
    producer.start()
    assert capture.wait_for_first_capture(timeout=1.0)

    stop_started_at = time.perf_counter()
    producer.stop()
    stop_elapsed = time.perf_counter() - stop_started_at

    # 1分の取得待機中でも、アプリ停止を即時反映できる予算とする。
    assert stop_elapsed < 0.5
