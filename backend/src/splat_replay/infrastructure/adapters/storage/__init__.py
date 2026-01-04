"""Storage adapters."""

from __future__ import annotations

from splat_replay.infrastructure.adapters.storage.settings_repository import (
    TomlSettingsRepository,
)
from splat_replay.infrastructure.adapters.storage.setup_state_file_adapter import (
    SetupStateFileAdapter,
)
from splat_replay.infrastructure.adapters.storage.setup_state_file_io import (
    SetupStateFileIO,
)
from splat_replay.infrastructure.adapters.storage.setup_state_serializer import (
    SetupStateSerializer,
)

__all__ = [
    "TomlSettingsRepository",
    "SetupStateFileAdapter",
    "SetupStateFileIO",
    "SetupStateSerializer",
]
