"""System adapters."""

from __future__ import annotations

from splat_replay.infrastructure.adapters.system.cross_cutting import (
    FileSystemPathsAdapter,
    LocalFileSystemAdapter,
    ProcessEnvironmentAdapter,
    StructlogLoggerAdapter,
    TomlConfigAdapter,
)
from splat_replay.infrastructure.adapters.system.gui_runtime_port_adapter import (
    GuiRuntimePortAdapter,
)
from splat_replay.infrastructure.adapters.system.system_command_adapter import (
    SystemCommandAdapter,
)
from splat_replay.infrastructure.adapters.system.system_power import (
    SystemPower,
)

__all__ = [
    # Port adapters (exported)
    "SystemCommandAdapter",
    "SystemPower",
    "GuiRuntimePortAdapter",
    # Cross-cutting concerns (exported for DI)
    "FileSystemPathsAdapter",
    "LocalFileSystemAdapter",
    "ProcessEnvironmentAdapter",
    "StructlogLoggerAdapter",
    "TomlConfigAdapter",
]
