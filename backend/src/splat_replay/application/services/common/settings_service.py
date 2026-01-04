from __future__ import annotations

from typing import List

from splat_replay.application.interfaces import (
    SectionUpdate,
    SettingSectionData,
    SettingsRepositoryPort,
)


class SettingsServiceError(Exception):
    """Base exception for settings service errors."""


class UnknownSettingsSectionError(SettingsServiceError):
    """Raised when a requested settings section does not exist."""

    def __init__(self, section_id: str) -> None:
        super().__init__(f"Unknown settings section: {section_id}")
        self.section_id = section_id


class UnknownSettingsFieldError(SettingsServiceError):
    """Raised when a requested settings field does not exist."""

    def __init__(self, section_id: str, field_id: str) -> None:
        super().__init__(f"Unknown settings field: {section_id}.{field_id}")
        self.section_id = section_id
        self.field_id = field_id


class SettingsService:
    """Application service that exposes settings metadata and persistence."""

    def __init__(self, repository: SettingsRepositoryPort) -> None:
        self._repository = repository

    def fetch_sections(self) -> List[SettingSectionData]:
        """Return all settings sections with field metadata and current values."""
        return self._repository.fetch_sections()

    def update_sections(self, updates: List[SectionUpdate]) -> None:
        """Persist provided settings section updates to the TOML settings file."""
        if not updates:
            return
        self._repository.update_sections(updates)


__all__ = [
    "SettingsService",
    "SettingsServiceError",
    "UnknownSettingsFieldError",
    "UnknownSettingsSectionError",
]
