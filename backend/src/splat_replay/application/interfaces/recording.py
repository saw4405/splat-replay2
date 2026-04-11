"""Recording-related ports (capture, recorder)."""

from __future__ import annotations

from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Callable,
    Literal,
    Optional,
    Protocol,
    Tuple,
)

from splat_replay.domain.models import Frame

if TYPE_CHECKING:
    from splat_replay.application.dto import ReplayBootstrapDTO
    from splat_replay.application.interfaces.data import (
        CaptureDeviceDescriptor,
        CaptureDeviceSettingsView,
        OBSSettingsView,
    )

# Type aliases
RecorderStatus = Literal["started", "paused", "resumed", "stopped"]


class CaptureDevicePort(Protocol):
    """Capture-device connectivity abstraction."""

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None: ...

    def is_connected(self) -> bool: ...


class CaptureDeviceEnumeratorPort(Protocol):
    """Capture-device enumeration abstraction."""

    def list_video_devices(self) -> list[str]: ...

    def list_video_device_descriptors(
        self,
    ) -> list[CaptureDeviceDescriptor]: ...


class CapturePort(Protocol):
    """Port for reading frames from the configured capture source."""

    def setup(self) -> None: ...

    def capture(self) -> Optional[Frame]: ...

    def current_time_seconds(self) -> Optional[float]: ...

    def teardown(self) -> None: ...


class VideoRecorderPort(Protocol):
    """Port for controlling the external recorder (OBS)."""

    def update_settings(self, settings: OBSSettingsView) -> None: ...

    async def setup(self) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> Optional[Path]: ...

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...

    async def teardown(self) -> None: ...

    def add_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...

    def remove_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...


class RecorderWithTranscriptionPort(Protocol):
    """Port for a recorder bundled with transcription support."""

    async def setup(self) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> Tuple[Optional[Path], Optional[Path]]: ...

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...

    async def cancel(self) -> None: ...

    async def teardown(self) -> None: ...

    def add_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...

    def remove_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...


class ReplayBootstrapResolverPort(Protocol):
    """Port for resolving replay bootstrap data in E2E/test-input mode."""

    def resolve(self) -> ReplayBootstrapDTO | None: ...
