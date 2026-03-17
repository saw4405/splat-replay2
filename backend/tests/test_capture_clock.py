from __future__ import annotations

from typing import Optional

import pytest

import splat_replay.infrastructure.adapters.system.capture_clock as capture_clock_module
from splat_replay.infrastructure.adapters.system.capture_clock import (
    CaptureClock,
)


class _ReplayCapture:
    def __init__(self, positions: list[Optional[float]]) -> None:
        self._positions = positions
        self._index = 0

    def setup(self) -> None:
        return None

    def capture(self):
        return None

    def current_time_seconds(self) -> Optional[float]:
        position = self._positions[min(self._index, len(self._positions) - 1)]
        self._index += 1
        return position

    def teardown(self) -> None:
        return None


def test_capture_clock_anchors_replay_time_to_wall_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall_times = iter([100.0, 200.0])
    monkeypatch.setattr(
        capture_clock_module.time,
        "time",
        lambda: next(wall_times),
    )
    clock = CaptureClock(_ReplayCapture([10.0, 12.5, 1.0]))

    first = clock.now()
    second = clock.now()
    third = clock.now()

    assert first == pytest.approx(100.0)
    assert second == pytest.approx(102.5)
    assert third == pytest.approx(200.0)


def test_capture_clock_falls_back_to_wall_clock_without_replay_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(capture_clock_module.time, "time", lambda: 123.0)
    clock = CaptureClock(_ReplayCapture([None]))

    assert clock.now() == pytest.approx(123.0)
