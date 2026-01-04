"""Setup services."""

from __future__ import annotations

from splat_replay.application.services.setup.setup_errors import SetupError
from splat_replay.application.services.setup.setup_service import SetupService
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
    SystemCheckService,
)
from splat_replay.application.services.setup.system_setup_service import (
    SystemSetupService,
)

__all__ = [
    "SetupError",
    "SetupService",
    "SoftwareCheckResult",
    "SystemCheckService",
    "SystemSetupService",
]
