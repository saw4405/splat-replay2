"""Infrastructure frame hub (moved)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from splat_replay.domain.models import Frame


@dataclass(slots=True)
class FramePacket:
    frame: Frame
    ts: float


class FrameHub:
    def __init__(self) -> None:
        self._latest: Optional[FramePacket] = None
        self._lock = threading.Lock()
        self._listeners: List[Callable[[FramePacket], None]] = []

    def publish(self, frame: Frame) -> None:
        pkt = FramePacket(frame=frame, ts=time.time())
        with self._lock:
            self._latest = pkt
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(pkt)
            except Exception:
                pass

    def get_latest(self) -> Optional[FramePacket]:
        with self._lock:
            return self._latest

    def add_listener(self, cb: Callable[[FramePacket], None]) -> None:
        with self._lock:
            self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[FramePacket], None]) -> None:
        with self._lock:
            if cb in self._listeners:
                self._listeners.remove(cb)


__all__ = ["FrameHub", "FramePacket"]
