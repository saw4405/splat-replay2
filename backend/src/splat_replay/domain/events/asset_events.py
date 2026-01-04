"""Asset-related domain events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from splat_replay.domain.events.base import DomainEvent


@dataclass(frozen=True)
class AssetRecordedSaved(DomainEvent):
    """Recorded asset has been saved."""

    EVENT_TYPE: ClassVar[str] = "domain.asset.recorded.saved"

    video: str = ""
    has_subtitle: bool = False
    has_thumbnail: bool = False
    started_at: str | None = None


@dataclass(frozen=True)
class AssetRecordedDeleted(DomainEvent):
    """Recorded asset has been deleted."""

    EVENT_TYPE: ClassVar[str] = "domain.asset.recorded.deleted"

    video: str = ""


@dataclass(frozen=True)
class AssetRecordedMetadataUpdated(DomainEvent):
    """Recorded asset metadata has been updated."""

    EVENT_TYPE: ClassVar[str] = "domain.asset.recorded.metadata_updated"

    video: str = ""


@dataclass(frozen=True)
class AssetRecordedSubtitleUpdated(DomainEvent):
    """Recorded asset subtitle has been updated."""

    EVENT_TYPE: ClassVar[str] = "domain.asset.recorded.subtitle_updated"

    video: str = ""


@dataclass(frozen=True)
class AssetEditedSaved(DomainEvent):
    """Edited asset has been saved."""

    EVENT_TYPE: ClassVar[str] = "domain.asset.edited.saved"

    video: str = ""


@dataclass(frozen=True)
class AssetEditedDeleted(DomainEvent):
    """Edited asset has been deleted."""

    EVENT_TYPE: ClassVar[str] = "domain.asset.edited.deleted"

    video: str = ""


__all__ = [
    "AssetRecordedSaved",
    "AssetRecordedDeleted",
    "AssetRecordedMetadataUpdated",
    "AssetRecordedSubtitleUpdated",
    "AssetEditedSaved",
    "AssetEditedDeleted",
]
