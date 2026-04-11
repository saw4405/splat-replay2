"""Service for preparing the external video recorder (OBS)."""

from __future__ import annotations

from typing import TypedDict

from splat_replay.application.interfaces import (
    CaptureDeviceSettingsView,
    ConfigPort,
    LoggerPort,
    OBSSettingsView,
    VideoRecorderPort,
)


class OBSConfig(TypedDict):
    """OBS settings DTO exposed to the web interface."""

    websocket_password: str
    capture_device_name: str


class RecordingPreparationService:
    """Coordinates OBS startup and virtual camera activation."""

    def __init__(
        self,
        recorder: VideoRecorderPort,
        config: ConfigPort,
        logger: LoggerPort,
    ) -> None:
        self._recorder = recorder
        self._config = config
        self._logger = logger

    async def prepare_recording(self) -> None:
        """Launch OBS if necessary and ensure the virtual camera is active."""
        self._logger.info("Preparing OBS for recording session")
        await self._recorder.setup()

    def update_settings(self, settings: OBSSettingsView) -> None:
        """Update recorder settings without restarting the app."""
        self._logger.info("Updating OBS recorder settings")
        self._recorder.update_settings(settings)

    def reload_obs_settings(self) -> None:
        """Reload OBS settings from the persisted configuration."""
        self.update_settings(self._config.get_obs_settings())

    def get_obs_config(self) -> OBSConfig:
        """Return the OBS config needed by setup UI."""
        obs_settings = self._config.get_obs_settings()
        device_settings = self._config.get_capture_device_settings()

        password = obs_settings.websocket_password
        password_str = (
            password.get_secret_value()
            if hasattr(password, "get_secret_value")
            else str(password)
        )

        return OBSConfig(
            websocket_password=password_str,
            capture_device_name=device_settings.name,
        )

    def get_capture_device_settings(self) -> CaptureDeviceSettingsView:
        """Return persisted capture-device settings."""
        return self._config.get_capture_device_settings()

    def save_obs_websocket_password(self, password: str) -> None:
        """Persist the OBS WebSocket password and refresh recorder config."""
        self._config.save_obs_websocket_password(password)
        self.update_settings(self._config.get_obs_settings())
        self._logger.info("OBS WebSocket password saved")

    def save_capture_device(self, device_name: str) -> None:
        """Persist only the selected capture-device name."""
        self._config.save_capture_device_binding(device_name)
        self._logger.info("Capture device saved", device=device_name)
