"""Infrastructure adapter implementing EventBusPort using EventBus."""

from __future__ import annotations

from typing import Iterable, Mapping, cast

from splat_replay.application.interfaces.messaging import (
    EventBusPort,
    EventSubscription,
)
from splat_replay.domain.events import DomainEvent
from splat_replay.infrastructure.messaging import Event, EventBus


class EventBusPortAdapter(EventBusPort):
    """Bridge EventBusPort to the in-memory EventBus implementation."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def publish(
        self, event_type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        self._bus.publish(Event(type=event_type, payload=dict(payload or {})))

    def publish_domain_event(self, event: DomainEvent) -> None:
        """ドメインイベントを発行する。"""
        payload: dict[str, object] = {
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "aggregate_id": event.aggregate_id,
            "correlation_id": event.correlation_id,
            **{
                key: value
                for key, value in vars(event).items()
                if key
                not in {
                    "event_id",
                    "timestamp",
                    "aggregate_id",
                    "correlation_id",
                }
            },
        }
        self._bus.publish(Event(type=event.get_event_type(), payload=payload))

    def subscribe(
        self, event_types: Iterable[str] | None = None
    ) -> EventSubscription:
        return cast(
            EventSubscription, self._bus.subscribe(event_types=event_types)
        )


__all__ = ["EventBusPortAdapter"]
