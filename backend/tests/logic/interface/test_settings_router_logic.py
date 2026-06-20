"""Settings Router Logic Tests."""

from __future__ import annotations

import sys
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from splat_replay.application.interfaces import (
    CaptureDeviceDiagnostics,
    CaptureDeviceRecoveryResult,
    CaptureDeviceRecoveryTrigger,
)

# ``src`` ディレクトリを ``sys.path`` へ追加
BASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE / "src"))

from splat_replay.interface.web.routers.settings import (
    create_settings_router,
)

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


def _route_by_path(router, path: str):
    for route in router.routes:
        if route.path == path:
            return route
    raise ValueError(f"Route not found for path: {path}")


@pytest.mark.asyncio
async def test_get_device_status_offloads_sync_check_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _DummyLogger:
        def error(self, event: str, **kw: object) -> None:
            _ = event, kw

    class _DummyDeviceChecker:
        def is_connected(self) -> bool:
            return True

    class _DummyServer:
        def __init__(self) -> None:
            self.device_checker = _DummyDeviceChecker()
            self.logger = _DummyLogger()

    called: list[object] = []

    async def _fake_to_thread(func, /, *args, **kwargs):
        called.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _fake_to_thread)

    server = cast("WebAPIServer", _DummyServer())
    router = create_settings_router(server)
    route = _route_by_path(router, "/api/device/status")

    response = await route.endpoint()

    assert response.body == b"true"
    assert called == [server.device_checker.is_connected]


@pytest.mark.asyncio
async def test_post_device_recover_offloads_sync_recovery_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from splat_replay.interface.web.schemas import (
        CaptureDeviceRecoveryRequest,
    )

    class _DummyLogger:
        def error(self, event: str, **kw: object) -> None:
            _ = event, kw

    class _DummyDeviceChecker:
        def recover_device(
            self, trigger: CaptureDeviceRecoveryTrigger
        ) -> CaptureDeviceRecoveryResult:
            return CaptureDeviceRecoveryResult(
                trigger=trigger,
                attempted=True,
                recovered=False,
                message="recover failed",
                action="restart-device",
            )

    class _DummyServer:
        def __init__(self) -> None:
            self.device_checker = _DummyDeviceChecker()
            self.logger = _DummyLogger()

    called: list[tuple[object, tuple[object, ...]]] = []

    async def _fake_to_thread(func, /, *args, **kwargs):
        called.append((func, args))
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _fake_to_thread)

    server = cast("WebAPIServer", _DummyServer())
    router = create_settings_router(server)
    route = _route_by_path(router, "/api/device/recover")

    response = await route.endpoint(
        CaptureDeviceRecoveryRequest(trigger="manual")
    )

    assert response.attempted is True
    assert response.recovered is False
    assert called == [(server.device_checker.recover_device, ("manual",))]


@pytest.mark.asyncio
async def test_get_device_diagnostics_offloads_sync_lookup_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _DummyLogger:
        def error(self, event: str, **kw: object) -> None:
            _ = event, kw

    class _DummyDeviceChecker:
        def get_diagnostics(self) -> CaptureDeviceDiagnostics:
            return CaptureDeviceDiagnostics(
                configured_device_name="MiraBox Capture",
                configured_hardware_id="USB\\VID_534D&PID_2109",
                configured_location_path="PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(3)#USB(2)",
                configured_parent_instance_id="USB\\VID_534D&PID_2109\\6&23427119&0&2",
                resolved_device=None,
                available_devices=[],
                last_recovery=None,
            )

    class _DummyServer:
        def __init__(self) -> None:
            self.device_checker = _DummyDeviceChecker()
            self.logger = _DummyLogger()

    called: list[object] = []

    async def _fake_to_thread(func, /, *args, **kwargs):
        called.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _fake_to_thread)

    server = cast("WebAPIServer", _DummyServer())
    router = create_settings_router(server)
    route = _route_by_path(router, "/api/device/diagnostics")

    response = await route.endpoint()

    assert response.configured_device_name == "MiraBox Capture"
    assert called == [server.device_checker.get_diagnostics]
