"""Recording-related domain events.

Events related to recording session lifecycle and state changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from splat_replay.domain.events.base import DomainEvent


@dataclass(frozen=True)
class RecordingStarted(DomainEvent):
    """Recording session has been started."""

    EVENT_TYPE: ClassVar[str] = "domain.recording.started"

    session_id: str = ""
    game_mode: str | None = None
    rate: str | None = None


@dataclass(frozen=True)
class RecordingPaused(DomainEvent):
    """Recording session has been paused."""

    EVENT_TYPE: ClassVar[str] = "domain.recording.paused"

    session_id: str = ""
    reason: str | None = None


@dataclass(frozen=True)
class RecordingResumed(DomainEvent):
    """Recording session has been resumed."""

    EVENT_TYPE: ClassVar[str] = "domain.recording.resumed"

    session_id: str = ""


@dataclass(frozen=True)
class RecordingStopped(DomainEvent):
    """Recording session has been stopped normally."""

    EVENT_TYPE: ClassVar[str] = "domain.recording.stopped"

    session_id: str = ""
    video_asset_id: str | None = None
    duration_seconds: float | None = None


@dataclass(frozen=True)
class RecordingCancelled(DomainEvent):
    """Recording session has been cancelled without saving."""

    EVENT_TYPE: ClassVar[str] = "domain.recording.cancelled"

    session_id: str = ""
    reason: str | None = None


@dataclass(frozen=True)
class RecordingMetadataUpdated(DomainEvent):
    """Recording metadata has been updated."""

    EVENT_TYPE: ClassVar[str] = "domain.recording.metadata_updated"

    metadata: dict[str, str | int | list[str] | None] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class PowerOffDetected(DomainEvent):
    """Switch power off has been detected."""

    EVENT_TYPE: ClassVar[str] = "domain.recording.power_off_detected"

    consecutive_count: int = 0
    threshold: int = 0
    final: bool = False


__all__ = [
    "RecordingStarted",
    "RecordingPaused",
    "RecordingResumed",
    "RecordingStopped",
    "RecordingCancelled",
    "RecordingMetadataUpdated",
    "PowerOffDetected",
]
