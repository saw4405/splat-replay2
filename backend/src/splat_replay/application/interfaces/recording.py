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
    from splat_replay.application.interfaces.data import (
        CaptureDeviceSettingsView,
        OBSSettingsView,
    )

# Type aliases
RecorderStatus = Literal["started", "paused", "resumed", "stopped"]


class CaptureDevicePort(Protocol):
    """キャプチャデバイスの接続確認を行うポート。"""

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None:
        """Update capture device settings."""
        ...

    def is_connected(self) -> bool:
        """Check if capture device is connected."""
        ...


class CaptureDeviceEnumeratorPort(Protocol):
    """キャプチャデバイスの列挙を行うポート。"""

    def list_video_devices(self) -> list[str]:
        """List available video capture devices."""
        ...


class CapturePort(Protocol):
    """キャプチャデバイスからの映像を取得するポート。"""

    def setup(self) -> None:
        """Setup capture device."""
        ...

    def capture(self) -> Optional[Frame]:
        """Capture a single frame."""
        ...

    def teardown(self) -> None:
        """Teardown capture device."""
        ...


class VideoRecorderPort(Protocol):
    """録画を制御するアウトバウンドポート（OBS等）。"""

    def update_settings(self, settings: OBSSettingsView) -> None:
        """Update recorder settings."""
        ...

    async def setup(self) -> None:
        """Setup recorder."""
        ...

    async def start(self) -> None:
        """Start recording."""
        ...

    async def stop(self) -> Optional[Path]:
        """Stop recording and return video path."""
        ...

    async def pause(self) -> None:
        """Pause recording."""
        ...

    async def resume(self) -> None:
        """Resume recording."""
        ...

    async def teardown(self) -> None:
        """Teardown recorder."""
        ...

    def add_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None:
        """Add status change listener."""
        ...

    def remove_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None:
        """Remove status change listener."""
        ...


class RecorderWithTranscriptionPort(Protocol):
    """録画+音声文字起こしを制御するポート。"""

    async def setup(self) -> None:
        """Setup recorder with transcription."""
        ...

    async def start(self) -> None:
        """Start recording with transcription."""
        ...

    async def stop(self) -> Tuple[Optional[Path], Optional[Path]]:
        """Stop recording and return (video_path, subtitle_path)."""
        ...

    async def pause(self) -> None:
        """Pause recording and transcription."""
        ...

    async def resume(self) -> None:
        """Resume recording and transcription."""
        ...

    async def cancel(self) -> None:
        """Cancel recording."""
        ...

    async def teardown(self) -> None:
        """Teardown recorder and transcription."""
        ...

    def add_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None:
        """Add status change listener."""
        ...

    def remove_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None:
        """Remove status change listener."""
        ...
