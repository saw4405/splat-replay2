from __future__ import annotations

from typing import Never, cast

from splat_replay.application.interfaces import (
    CaptureDeviceSettingsView,
    CaptureDeviceDescriptor,
    CaptureDeviceRecoveryResult,
    CommandResult,
    LoggerPort,
)
from splat_replay.application.services.system.device_checker import (
    DeviceChecker,
)
from splat_replay.domain.config import CaptureDeviceSettings


class _DummyLogger:
    def debug(self, event: str, **kw: object) -> None:
        pass

    def info(self, event: str, **kw: object) -> None:
        pass

    def warning(self, event: str, **kw: object) -> None:
        pass

    def error(self, event: str, **kw: object) -> None:
        pass

    def exception(self, event: str, **kw: object) -> None:
        pass


class _SpyLogger(_DummyLogger):
    def __init__(self) -> None:
        self.info_events: list[tuple[str, dict[str, object]]] = []
        self.warning_events: list[tuple[str, dict[str, object]]] = []

    def info(self, event: str, **kw: object) -> None:
        self.info_events.append((event, kw))

    def warning(self, event: str, **kw: object) -> None:
        self.warning_events.append((event, kw))


class _FakeCaptureDevicePort:
    def __init__(self, *, connected: bool = False) -> None:
        self.updated_settings: list[CaptureDeviceSettings] = []
        self.connected = connected

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None:
        self.updated_settings.append(cast(CaptureDeviceSettings, settings))

    def is_connected(self) -> bool:
        return self.connected


class _FakeCaptureDeviceEnumerator:
    def __init__(
        self, descriptor_sequence: list[list[CaptureDeviceDescriptor]]
    ) -> None:
        self._descriptor_sequence = descriptor_sequence
        self._calls = 0
        self._last_descriptors: list[CaptureDeviceDescriptor] = (
            descriptor_sequence[0] if descriptor_sequence else []
        )

    def list_video_device_descriptors(self) -> list[CaptureDeviceDescriptor]:
        if self._calls < len(self._descriptor_sequence):
            self._last_descriptors = self._descriptor_sequence[self._calls]
        self._calls += 1
        return list(self._last_descriptors)

    def list_video_devices(self) -> list[str]:
        return [descriptor.name for descriptor in self._last_descriptors]


class _FakeMicrophoneEnumerator:
    def list_microphones(self) -> list[str]:
        return []


class _FakeConfig:
    def __init__(self, settings: CaptureDeviceSettings) -> None:
        self._settings = settings

    def get_capture_device_settings(self) -> CaptureDeviceSettings:
        return self._settings

    def get_behavior_settings(self) -> Never:
        raise NotImplementedError

    def get_upload_settings(self) -> Never:
        raise NotImplementedError

    def get_video_edit_settings(self) -> Never:
        raise NotImplementedError

    def get_obs_settings(self) -> Never:
        raise NotImplementedError

    def save_obs_websocket_password(self, password: str) -> Never:
        _ = password
        raise NotImplementedError

    def save_capture_device_name(self, device_name: str) -> None:
        self.save_capture_device_binding(device_name)

    def save_capture_device_binding(
        self,
        device_name: str,
        hardware_id: str | None = None,
        location_path: str | None = None,
        parent_instance_id: str | None = None,
    ) -> None:
        self._settings = CaptureDeviceSettings(
            name=device_name,
            hardware_id=hardware_id,
            location_path=location_path,
            parent_instance_id=parent_instance_id,
        )

    def save_upload_privacy_status(self, privacy_status: str) -> Never:
        _ = privacy_status
        raise NotImplementedError


class _FakeSystemCommandPort:
    def __init__(
        self,
        *,
        exists: bool = True,
        results: list[CommandResult] | None = None,
    ) -> None:
        self._exists = exists
        self.commands: list[list[str]] = []
        self._results = results or []

    def check_command_exists(self, command: str) -> bool:
        return self._exists and command == "pnputil"

    def execute_command(
        self,
        command: list[str],
        timeout: float | None = None,
    ) -> CommandResult:
        self.commands.append(command)
        if self._results:
            return self._results.pop(0)
        return CommandResult(return_code=0, stdout="", stderr="")


def _build_descriptor(
    *,
    name: str = "MiraBox Capture",
    hardware_id: str = "USB\\VID_534D&PID_2109",
    location_path: str = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(3)#USB(2)",
    parent_instance_id: str = "USB\\VID_534D&PID_2109\\6&23427119&0&2",
    pnp_instance_id: str = "USB\\VID_534D&PID_2109&MI_00\\7&2B9027F5&0&0000",
) -> CaptureDeviceDescriptor:
    return CaptureDeviceDescriptor(
        name=name,
        alternative_name="@device_pnp_mock",
        pnp_instance_id=pnp_instance_id,
        hardware_id=hardware_id,
        location_path=location_path,
        parent_instance_id=parent_instance_id,
    )


def _build_checker(
    *,
    settings: CaptureDeviceSettings,
    descriptor_sequence: list[list[CaptureDeviceDescriptor]],
    system_commands: _FakeSystemCommandPort | None = None,
    device_connected: bool = False,
    logger: LoggerPort | None = None,
) -> tuple[DeviceChecker, _FakeConfig, _FakeCaptureDevicePort]:
    config = _FakeConfig(settings)
    device = _FakeCaptureDevicePort(connected=device_connected)
    checker = DeviceChecker(
        device=device,
        enumerator=_FakeCaptureDeviceEnumerator(descriptor_sequence),
        microphone_enumerator=_FakeMicrophoneEnumerator(),
        logger=logger or cast(LoggerPort, _DummyLogger()),
        config=config,
        system_commands=system_commands or _FakeSystemCommandPort(),
    )
    return checker, config, device


def test_save_selected_device_binds_hidden_fields() -> None:
    descriptor = _build_descriptor(name="New Capture Device")
    checker, config, device = _build_checker(
        settings=CaptureDeviceSettings(name="Old Device"),
        descriptor_sequence=[[descriptor]],
    )

    result = checker.save_selected_device("New Capture Device")

    assert result.binding_status == "bound"
    saved = config.get_capture_device_settings()
    assert saved.name == "New Capture Device"
    assert saved.hardware_id == descriptor.hardware_id
    assert saved.location_path == descriptor.location_path
    assert saved.parent_instance_id == descriptor.parent_instance_id
    assert device.updated_settings[-1] == saved


def test_rebind_configured_device_clears_stale_hidden_fields_when_name_not_found() -> (
    None
):
    checker, config, device = _build_checker(
        settings=CaptureDeviceSettings(
            name="Replacement Device",
            hardware_id="USB\\VID_OLD&PID_0001",
            location_path="PCIROOT(0)#OLD",
            parent_instance_id="USB\\VID_OLD&PID_0001\\PARENT",
        ),
        descriptor_sequence=[[]],
    )

    result = checker.rebind_configured_device()

    assert result.binding_status == "name_only"
    saved = config.get_capture_device_settings()
    assert saved.name == "Replacement Device"
    assert saved.hardware_id is None
    assert saved.location_path is None
    assert saved.parent_instance_id is None
    assert device.updated_settings[-1] == saved


def test_is_connected_supplements_binding_when_name_only_setting_matches() -> (
    None
):
    descriptor = _build_descriptor(name="MiraBox Capture")
    checker, config, device = _build_checker(
        settings=CaptureDeviceSettings(name="MiraBox Capture"),
        descriptor_sequence=[[descriptor]],
    )

    connected = checker.is_connected()

    assert connected is True
    saved = config.get_capture_device_settings()
    assert saved.hardware_id == descriptor.hardware_id
    assert saved.location_path == descriptor.location_path
    assert saved.parent_instance_id == descriptor.parent_instance_id
    assert device.updated_settings[-1] == saved


def test_is_connected_falls_back_to_device_port_when_descriptor_is_unresolved() -> (
    None
):
    checker, config, device = _build_checker(
        settings=CaptureDeviceSettings(name="Capture Device"),
        descriptor_sequence=[[]],
        device_connected=True,
    )

    connected = checker.is_connected()

    assert connected is True
    saved = config.get_capture_device_settings()
    assert saved.name == "Capture Device"
    assert saved.hardware_id is None
    assert saved.location_path is None
    assert saved.parent_instance_id is None
    assert device.updated_settings == []


def test_recover_device_restarts_bound_parent_device_and_waits_for_reappearance() -> (
    None
):
    descriptor = _build_descriptor()
    commands = _FakeSystemCommandPort()
    logger = _SpyLogger()
    checker, _, _ = _build_checker(
        settings=CaptureDeviceSettings(
            name=descriptor.name,
            hardware_id=descriptor.hardware_id,
            location_path=descriptor.location_path,
            parent_instance_id=descriptor.parent_instance_id,
        ),
        descriptor_sequence=[[], [], [descriptor]],
        system_commands=commands,
        logger=cast(LoggerPort, logger),
    )

    result = checker.recover_device(trigger="manual")

    assert result == CaptureDeviceRecoveryResult(
        trigger="manual",
        attempted=True,
        recovered=True,
        message="Capture device recovered",
        action="restart-device",
    )
    assert commands.commands == [
        ["pnputil", "/scan-devices"],
        ["pnputil", "/restart-device", descriptor.parent_instance_id],
    ]
    assert logger.info_events[0] == (
        "Capture device recovery started",
        {
            "trigger": "manual",
            "device_name": descriptor.name,
            "parent_instance_id": descriptor.parent_instance_id,
        },
    )
    assert logger.info_events[-1] == (
        "Capture device recovery succeeded",
        {
            "trigger": "manual",
            "action": "restart-device",
            "message": "Capture device recovered",
        },
    )


def test_recover_device_logs_failure_result() -> None:
    descriptor = _build_descriptor()
    commands = _FakeSystemCommandPort(
        results=[
            CommandResult(return_code=0, stdout="", stderr=""),
            CommandResult(return_code=1, stdout="", stderr="restart failed"),
        ]
    )
    logger = _SpyLogger()
    checker, _, _ = _build_checker(
        settings=CaptureDeviceSettings(
            name=descriptor.name,
            hardware_id=descriptor.hardware_id,
            location_path=descriptor.location_path,
            parent_instance_id=descriptor.parent_instance_id,
        ),
        descriptor_sequence=[[descriptor]],
        system_commands=commands,
        logger=cast(LoggerPort, logger),
    )

    result = checker.recover_device(trigger="manual")

    assert result == CaptureDeviceRecoveryResult(
        trigger="manual",
        attempted=True,
        recovered=False,
        message="Device restart failed",
        action="restart-device",
    )
    assert logger.info_events[0] == (
        "Capture device recovery started",
        {
            "trigger": "manual",
            "device_name": descriptor.name,
            "parent_instance_id": descriptor.parent_instance_id,
        },
    )
    assert logger.warning_events[-1] == (
        "Capture device recovery failed",
        {
            "trigger": "manual",
            "action": "restart-device",
            "message": "Device restart failed",
        },
    )
