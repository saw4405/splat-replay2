"""Messaging ports (events, commands, frames)."""

from __future__ import annotations

from typing import Callable, Mapping, Optional, Protocol, Set

from splat_replay.domain.events import DomainEvent
from splat_replay.domain.models import Frame


class EventPublisher(Protocol):
    """Publish events to event bus (legacy string-based)."""

    def publish(
        self, event_type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        """Publish event with type and payload."""
        ...


class DomainEventPublisher(Protocol):
    """Publish domain events to event bus (type-safe)."""

    def publish_domain_event(self, event: DomainEvent) -> None:
        """Publish domain event object."""
        ...


class EventBusPort(Protocol):
    """Event bus port - combines publishing and subscription.

    Interface層がInfrastructure層のEventBusに直接依存しないための抽象化。
    EventPublisher + DomainEventPublisher + EventSubscriberの統合ポート。
    """

    def publish(
        self, event_type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        """Publish event with type and payload (legacy)."""
        ...

    def publish_domain_event(self, event: DomainEvent) -> None:
        """Publish domain event object (type-safe)."""
        ...

    def subscribe(
        self, event_types: Optional[Set[str]] = None
    ) -> EventSubscription:
        """Subscribe to event types (or all if None)."""
        ...


class EventSubscription(Protocol):
    """Event subscription handle."""

    def poll(self, max_items: int = 100) -> list[object]:
        """Poll events from subscription."""
        ...

    def close(self) -> None:
        """Close subscription."""
        ...


class EventSubscriber(Protocol):
    """Subscribe to events from event bus."""

    def subscribe(
        self, event_types: Optional[Set[str]] = None
    ) -> EventSubscription:
        """Subscribe to event types (or all if None)."""
        ...


class FramePublisher(Protocol):
    """Publish frames to frame hub."""

    def publish_frame(self, frame: Frame) -> None:
        """Publish frame to subscribers."""
        ...


class FrameSource(Protocol):
    """Frame source for subscribers."""

    def add_listener(self, cb: Callable[[Frame], None]) -> None:
        """Add frame listener callback."""
        ...

    def remove_listener(self, cb: Callable[[Frame], None]) -> None:
        """Remove frame listener callback."""
        ...

    def get_latest(self) -> Optional[Frame]:
        """Get latest published frame."""
        ...


class CommandDispatcher(Protocol):
    """Dispatch commands to command bus."""

    def submit(self, name: str, **payload: object) -> object:
        """Submit command and return Future-like object."""
        ...

    async def dispatch(self, name: str, **payload: object) -> object:
        """Submit command and await completion."""
        ...
