"""Video capture device enumerator for Windows."""

from __future__ import annotations

from typing import List

from structlog.stdlib import BoundLogger

from splat_replay.infrastructure.adapters.ffmpeg_processor import (
    FFmpegProcessor,
)


class VideoDeviceEnumerator:
    """Enumerate video capture devices using FFmpegProcessor."""

    def __init__(
        self,
        ffmpeg_processor: FFmpegProcessor,
        logger: BoundLogger,
    ) -> None:
        self._ffmpeg_processor = ffmpeg_processor
        self.logger = logger

    def list_devices(self) -> List[str]:
        """List available video capture devices.

        Returns:
            List of device names
        """
        try:
            # Use FFmpegProcessor's async method synchronously
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            devices = loop.run_until_complete(
                self._ffmpeg_processor.list_video_devices()
            )

            return devices

        except Exception as e:
            self.logger.error(
                "Failed to enumerate video devices", error=str(e)
            )
            return []
