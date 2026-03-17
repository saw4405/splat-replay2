from __future__ import annotations

import time

from splat_replay.application.interfaces import CapturePort, ClockPort

REPLAY_RESET_TOLERANCE_SECONDS = 1.0


class CaptureClock(ClockPort):
    """入力ソースに追従する時計。

    live_capture は壁時計を返し、video_file は入力動画の再生位置を
    壁時計へアンカーした擬似時刻として返す。
    """

    def __init__(self, capture: CapturePort) -> None:
        self._capture = capture
        self._replay_anchor_seconds: float | None = None
        self._last_replay_seconds: float | None = None

    def now(self) -> float:
        replay_seconds = self._capture.current_time_seconds()
        if replay_seconds is None:
            self._replay_anchor_seconds = None
            self._last_replay_seconds = None
            return time.time()

        if self._should_reset_anchor(replay_seconds):
            self._replay_anchor_seconds = time.time() - replay_seconds

        self._last_replay_seconds = replay_seconds
        anchor_seconds = self._replay_anchor_seconds
        if anchor_seconds is None:
            anchor_seconds = time.time() - replay_seconds
            self._replay_anchor_seconds = anchor_seconds
        return anchor_seconds + replay_seconds

    def _should_reset_anchor(self, replay_seconds: float) -> bool:
        if self._replay_anchor_seconds is None:
            return True
        last_replay_seconds = self._last_replay_seconds
        if last_replay_seconds is None:
            return True
        return (
            replay_seconds + REPLAY_RESET_TOLERANCE_SECONDS
            < last_replay_seconds
        )
