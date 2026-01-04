"""System services."""

from __future__ import annotations

from splat_replay.application.services.system.device_checker import (
    DeviceChecker,
)
from splat_replay.application.services.system.power_manager import PowerManager
from splat_replay.application.services.system.software_checker import (
    SoftwareChecker,
)

__all__ = [
    "DeviceChecker",
    "PowerManager",
    "SoftwareChecker",
]
