"""Infrastructure runtime event bus (moved from runtime/ to infrastructure/runtime/).

Thread-safe in-memory publish/subscribe bus. Domain & application should depend
only on abstract EventPublisher; this module is an infra detail.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable, Protocol


@dataclass(slots=True)
class Event:
    type: str
    payload: dict[str, object] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    ts: float = field(default_factory=time.time)
    severity: str = "info"
    correlation_id: uuid.UUID | None = None


class Subscription(Protocol):
    def poll(self, max_items: int | None = None) -> list[Event]: ...
    def close(self) -> None: ...


class _Subscription:
    def __init__(self, types: set[str] | None, maxlen: int, drop_oldest: bool):
        self.types = types
        self._queue: Deque[Event] = deque()
        self._lock = threading.Lock()
        self._closed = False
        self.maxlen = maxlen
        self.drop_oldest = drop_oldest

    def match(self, ev: Event) -> bool:
        return self.types is None or ev.type in self.types

    def enqueue(self, ev: Event) -> None:
        with self._lock:
            if self._closed:
                return
            if len(self._queue) >= self.maxlen:
                if self.drop_oldest:
                    self._queue.popleft()
                else:
                    return
            self._queue.append(ev)

    def poll(self, max_items: int | None = None) -> list[Event]:
        out: list[Event] = []
        with self._lock:
            if self._closed:
                return out
            n = (
                len(self._queue)
                if max_items is None
                else min(len(self._queue), max_items)
            )
            for _ in range(n):
                out.append(self._queue.popleft())
        return out

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._queue.clear()


class EventBus:
    def __init__(self) -> None:
        self._subs: list[_Subscription] = []
        self._lock = threading.Lock()

    def publish(self, ev: Event) -> None:
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            if sub.match(ev):
                sub.enqueue(ev)

    def subscribe(
        self,
        *,
        event_types: Iterable[str] | None = None,
        max_queue: int = 200,
        drop_oldest: bool = True,
    ) -> Subscription:
        types = set(event_types) if event_types is not None else None
        sub = _Subscription(types, max_queue, drop_oldest)
        with self._lock:
            self._subs.append(sub)
        return sub

    def unsubscribe(self, sub: _Subscription) -> None:
        with self._lock:
            if sub in self._subs:
                self._subs.remove(sub)
        sub.close()


__all__ = ["Event", "EventBus", "Subscription"]
