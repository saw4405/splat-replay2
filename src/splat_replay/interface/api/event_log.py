"""イベントバスから最新イベントを蓄積するヘルパー。"""

from __future__ import annotations

import threading
from collections import deque
from typing import Deque, Iterable, List, Optional

from splat_replay.infrastructure.runtime.events import (
    Event,
    EventBus,
    Subscription,
)


class EventLog:
    """イベントを購読し、最新の一定件数を保持する。"""

    def __init__(
        self,
        bus: EventBus,
        *,
        max_events: int = 500,
        event_types: Iterable[str] | None = None,
    ) -> None:
        self._subscription: Subscription = bus.subscribe(
            event_types=event_types,
            max_queue=max_events * 4,
            drop_oldest=True,
        )
        self._events: Deque[Event] = deque(maxlen=max_events)
        self._lock = threading.Lock()

    def _drain(self) -> None:
        items = self._subscription.poll()
        if not items:
            return
        with self._lock:
            self._events.extend(items)

    def list(self, after_ts: Optional[float] = None) -> List[Event]:
        """条件に合致するイベントを取得する。"""

        self._drain()
        with self._lock:
            snapshot = list(self._events)
        if after_ts is None:
            return snapshot
        return [ev for ev in snapshot if ev.ts > after_ts]

    def close(self) -> None:
        """購読を明示的に解除する。"""

        self._subscription.close()
        with self._lock:
            self._events.clear()


__all__ = ["EventLog"]
