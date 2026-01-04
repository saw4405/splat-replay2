"""Base domain event definition.

Domain events represent something that happened in the domain.
They are immutable and should be named in past tense.

Design principles:
- Immutable (frozen dataclass)
- Past tense naming (e.g., BattleStarted, not BattleStart)
- Contains only domain-relevant information
- No infrastructure dependencies
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events.

    Attributes:
        event_id: Unique identifier for this event instance
        timestamp: Unix timestamp when the event occurred
        aggregate_id: ID of the aggregate that generated this event (optional)
        correlation_id: ID linking related events across aggregates (optional)
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    aggregate_id: str | None = None
    correlation_id: str | None = None

    # Class variable to identify event type for routing
    # Subclasses should override this
    EVENT_TYPE: ClassVar[str] = "domain.base_event"

    def get_event_type(self) -> str:
        """Get the event type for routing/filtering."""
        return self.__class__.EVENT_TYPE


__all__ = ["DomainEvent"]
