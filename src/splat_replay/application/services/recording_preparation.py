"""Service for preparing the external video recorder (OBS)."""

from __future__ import annotations

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import VideoRecorderPort


class RecordingPreparationService:
    """Coordinates OBS startup and virtual camera activation."""

    def __init__(
        self, recorder: VideoRecorderPort, logger: BoundLogger
    ) -> None:
        self._recorder = recorder
        self._logger = logger

    async def prepare_recording(self) -> None:
        """Launch OBS if necessary and ensure the virtual camera is active."""
        self._logger.info("Preparing OBS for recording session")
        await self._recorder.setup()
