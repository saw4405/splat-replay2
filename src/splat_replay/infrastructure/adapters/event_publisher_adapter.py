"""Infrastructure adapter implementing EventPublisher using EventBus."""

from __future__ import annotations

from typing import Mapping

from splat_replay.application.interfaces import EventPublisher
from splat_replay.infrastructure.runtime.events import Event, EventBus


class EventPublisherAdapter(EventPublisher):
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def publish(
        self, event_type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        self._bus.publish(Event(type=event_type, payload=dict(payload or {})))


__all__ = ["EventPublisherAdapter"]
