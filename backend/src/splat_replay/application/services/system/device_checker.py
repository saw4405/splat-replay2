"""Application service for capture-device state, rebinding, and recovery."""

from __future__ import annotations

import asyncio
import sys
import time

from splat_replay.application.interfaces import (
    CaptureDeviceBindingResult,
    CaptureDeviceDescriptor,
    CaptureDeviceDiagnostics,
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CaptureDeviceRecoveryResult,
    CaptureDeviceRecoveryTrigger,
    CaptureDeviceSettingsView,
    ConfigPort,
    LoggerPort,
    MicrophoneEnumeratorPort,
    SystemCommandPort,
)


class DeviceChecker:
    """Service that coordinates capture-device status and recovery."""

    def __init__(
        self,
        device: CaptureDevicePort,
        enumerator: CaptureDeviceEnumeratorPort,
        microphone_enumerator: MicrophoneEnumeratorPort,
        logger: LoggerPort,
        config: ConfigPort,
        system_commands: SystemCommandPort,
    ) -> None:
        self.device = device
        self._enumerator = enumerator
        self._microphone_enumerator = microphone_enumerator
        self.logger = logger
        self._config = config
        self._system_commands = system_commands
        self._last_recovery: CaptureDeviceRecoveryResult | None = None

    def _complete_recovery(
        self,
        *,
        trigger: CaptureDeviceRecoveryTrigger,
        attempted: bool,
        recovered: bool,
        message: str,
        action: str,
    ) -> CaptureDeviceRecoveryResult:
        result = CaptureDeviceRecoveryResult(
            trigger=trigger,
            attempted=attempted,
            recovered=recovered,
            message=message,
            action=action,
        )
        self._last_recovery = result
        log_payload = {
            "trigger": trigger,
            "action": action,
            "message": message,
        }
        if recovered:
            self.logger.info(
                "Capture device recovery succeeded", **log_payload
            )
        else:
            self.logger.warning(
                "Capture device recovery failed", **log_payload
            )
        return result

    def _list_descriptors(self) -> list[CaptureDeviceDescriptor]:
        return self._enumerator.list_video_device_descriptors()

    def _resolve_unique_name_match(
        self,
        device_name: str,
        descriptors: list[CaptureDeviceDescriptor],
    ) -> CaptureDeviceDescriptor | None:
        matches = [
            descriptor
            for descriptor in descriptors
            if descriptor.name == device_name
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _resolve_configured_descriptor(
        self,
        settings: CaptureDeviceSettingsView,
        descriptors: list[CaptureDeviceDescriptor],
    ) -> CaptureDeviceDescriptor | None:
        if settings.hardware_id and settings.location_path:
            for descriptor in descriptors:
                if (
                    descriptor.hardware_id == settings.hardware_id.upper()
                    and descriptor.location_path
                    == settings.location_path.upper()
                ):
                    return descriptor
            return None

        return self._resolve_unique_name_match(settings.name, descriptors)

    def _persist_binding(
        self,
        device_name: str,
        descriptor: CaptureDeviceDescriptor | None,
    ) -> CaptureDeviceBindingResult:
        if descriptor is None:
            self._config.save_capture_device_binding(device_name)
            settings = self._config.get_capture_device_settings()
            self.device.update_settings(settings)
            result = CaptureDeviceBindingResult(
                device_name=device_name,
                binding_status="name_only",
                message="Capture device saved without binding metadata",
                matched_descriptor=None,
            )
            self.logger.info(
                "Capture device saved without hidden binding",
                device_name=device_name,
            )
            return result

        self._config.save_capture_device_binding(
            device_name,
            hardware_id=descriptor.hardware_id,
            location_path=descriptor.location_path,
            parent_instance_id=descriptor.parent_instance_id,
        )
        settings = self._config.get_capture_device_settings()
        self.device.update_settings(settings)
        result = CaptureDeviceBindingResult(
            device_name=device_name,
            binding_status="bound",
            message="Capture device bound",
            matched_descriptor=descriptor,
        )
        self.logger.info(
            "Capture device bound",
            device_name=device_name,
            hardware_id=descriptor.hardware_id,
            location_path=descriptor.location_path,
        )
        return result

    def save_selected_device(
        self, device_name: str
    ) -> CaptureDeviceBindingResult:
        """Persist a newly selected device and bind hidden recovery fields."""
        descriptor = self._resolve_unique_name_match(
            device_name, self._list_descriptors()
        )
        return self._persist_binding(device_name, descriptor)

    def rebind_configured_device(self) -> CaptureDeviceBindingResult:
        """Re-resolve hidden fields for the currently configured device name."""
        settings = self._config.get_capture_device_settings()
        descriptor = self._resolve_unique_name_match(
            settings.name, self._list_descriptors()
        )
        return self._persist_binding(settings.name, descriptor)

    def is_connected(self) -> bool:
        """Return whether the configured capture device is connected."""
        if sys.platform != "win32":
            return self.device.is_connected()

        settings = self._config.get_capture_device_settings()
        descriptors = self._list_descriptors()
        descriptor = self._resolve_configured_descriptor(settings, descriptors)
        if descriptor is None:
            return self.device.is_connected()

        if (
            settings.hardware_id is None
            or settings.location_path is None
            or settings.parent_instance_id != descriptor.parent_instance_id
        ):
            self._persist_binding(settings.name, descriptor)

        return True

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None:
        """Update the adapter-side settings without rebinding."""
        self.device.update_settings(settings)
        self.logger.info(
            "Capture device settings updated",
            device_name=settings.name,
        )

    def list_video_capture_devices(self) -> list[str]:
        """List display names of available video capture devices."""
        devices = self._enumerator.list_video_devices()
        self.logger.info("Video capture devices listed", count=len(devices))
        return devices

    def list_microphone_devices(self) -> list[str]:
        """List available microphones."""
        devices = self._microphone_enumerator.list_microphones()
        self.logger.info("Microphone devices listed", count=len(devices))
        return devices

    def recover_device(
        self, trigger: CaptureDeviceRecoveryTrigger
    ) -> CaptureDeviceRecoveryResult:
        """Attempt software recovery for the configured capture device."""
        settings = self._config.get_capture_device_settings()
        self.logger.info(
            "Capture device recovery started",
            trigger=trigger,
            device_name=settings.name,
            parent_instance_id=settings.parent_instance_id,
        )
        if sys.platform != "win32":
            return self._complete_recovery(
                trigger=trigger,
                attempted=False,
                recovered=False,
                message="Capture device recovery is only supported on Windows",
                action="unsupported-platform",
            )

        if not self._system_commands.check_command_exists("pnputil"):
            return self._complete_recovery(
                trigger=trigger,
                attempted=False,
                recovered=False,
                message="pnputil is not available",
                action="missing-command",
            )

        target_parent_instance_id = settings.parent_instance_id
        if not target_parent_instance_id:
            binding = self.rebind_configured_device()
            if binding.binding_status != "bound":
                return self._complete_recovery(
                    trigger=trigger,
                    attempted=False,
                    recovered=False,
                    message="Configured device could not be resolved for recovery",
                    action="resolve-device",
                )
            target_parent_instance_id = (
                binding.matched_descriptor.parent_instance_id
                if binding.matched_descriptor
                else None
            )

        if not target_parent_instance_id:
            return self._complete_recovery(
                trigger=trigger,
                attempted=False,
                recovered=False,
                message="Configured device has no restart target",
                action="resolve-device",
            )

        scan = self._system_commands.execute_command(
            ["pnputil", "/scan-devices"], timeout=15
        )
        if not scan.success:
            return self._complete_recovery(
                trigger=trigger,
                attempted=True,
                recovered=False,
                message="Device scan failed",
                action="scan-devices",
            )

        restart = self._system_commands.execute_command(
            ["pnputil", "/restart-device", target_parent_instance_id],
            timeout=20,
        )
        if not restart.success:
            return self._complete_recovery(
                trigger=trigger,
                attempted=True,
                recovered=False,
                message="Device restart failed",
                action="restart-device",
            )

        for _ in range(5):
            time.sleep(0.5)
            if self.is_connected():
                return self._complete_recovery(
                    trigger=trigger,
                    attempted=True,
                    recovered=True,
                    message="Capture device recovered",
                    action="restart-device",
                )

        return self._complete_recovery(
            trigger=trigger,
            attempted=True,
            recovered=False,
            message="Capture device did not reappear after restart",
            action="restart-device",
        )

    def get_diagnostics(self) -> CaptureDeviceDiagnostics:
        """Return current capture-device diagnostics."""
        settings = self._config.get_capture_device_settings()
        descriptors = self._list_descriptors()
        resolved = self._resolve_configured_descriptor(settings, descriptors)
        return CaptureDeviceDiagnostics(
            configured_device_name=settings.name,
            configured_hardware_id=settings.hardware_id,
            configured_location_path=settings.location_path,
            configured_parent_instance_id=settings.parent_instance_id,
            resolved_device=resolved,
            available_devices=descriptors,
            last_recovery=self._last_recovery,
        )

    async def wait_for_device_connection(
        self, timeout: float | None = None
    ) -> bool:
        """Wait until the configured capture device becomes connected."""
        start_time = time.time()
        while not await asyncio.to_thread(self.is_connected):
            elapsed = time.time() - start_time
            if timeout is not None and elapsed > timeout:
                self.logger.error(
                    "Capture device did not appear before timeout"
                )
                return False
            await asyncio.sleep(0.5)
        self.logger.info("Capture device connected")
        return True
