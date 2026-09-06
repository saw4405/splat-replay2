from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from structlog.stdlib import BoundLogger

from splat_replay.infrastructure.adapters.capture import capture_device_checker


def test_query_pnp_metadata_requests_only_required_properties(
    monkeypatch: Any,
) -> None:
    observed_commands: list[str] = []

    def powershell_json(command: str, timeout: float = 10) -> object:
        observed_commands.append(command)
        return {
            "location_paths": [
                "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(3)#USB(2)#USBMI(0)"
            ],
            "parent_instance_id": "USB\\VID_534D&PID_2109\\PARENT",
        }

    monkeypatch.setattr(capture_device_checker.sys, "platform", "win32")
    monkeypatch.setattr(
        capture_device_checker, "_powershell_json", powershell_json
    )

    metadata = capture_device_checker._query_pnp_metadata(
        "USB\\VID_534D&PID_2109&MI_00\\INSTANCE",
        Mock(spec=BoundLogger),
    )

    assert metadata == (
        "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(3)#USB(2)",
        "USB\\VID_534D&PID_2109\\PARENT",
    )
    assert len(observed_commands) == 1
    assert (
        "-KeyName 'DEVPKEY_Device_LocationPaths','DEVPKEY_Device_Parent'"
        in observed_commands[0]
    )
