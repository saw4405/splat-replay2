"""Infrastructure frame hub (moved)."""

from __future__ import annotations

import threading
from typing import Callable, List, Optional

from splat_replay.domain.models import Frame


class FrameHub:
    def __init__(self) -> None:
        self._latest: Optional[Frame] = None
        self._lock = threading.Lock()
        self._listeners: List[Callable[[Frame], None]] = []

    def publish(self, frame: Frame) -> None:
        with self._lock:
            self._latest = frame
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(frame)
            except Exception:
                pass

    def get_latest(self) -> Optional[Frame]:
        with self._lock:
            return self._latest

    def add_listener(self, cb: Callable[[Frame], None]) -> None:
        with self._lock:
            self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[Frame], None]) -> None:
        with self._lock:
            if cb in self._listeners:
                self._listeners.remove(cb)


__all__ = ["FrameHub"]
