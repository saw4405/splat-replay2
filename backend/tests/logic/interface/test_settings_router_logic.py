"""Settings router logic tests."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute

from splat_replay.interface.web.routers.settings import create_settings_router

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


def _route_by_path(router: APIRouter, path: str) -> APIRoute:
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == path:
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
