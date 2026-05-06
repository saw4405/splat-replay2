"""Remote access router contract tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from splat_replay.interface.web.routers.remote_access import (
    create_remote_access_router,
)

pytestmark = pytest.mark.contract


class _SettingsService:
    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    def fetch_remote_access_enabled(self) -> bool:
        return self._enabled


def _build_app(enabled: bool) -> FastAPI:
    app = FastAPI()
    server = SimpleNamespace(
        settings_service=_SettingsService(enabled),
    )
    app.include_router(create_remote_access_router(cast(Any, server)))
    return app


def test_remote_access_status_reports_restart_required_when_enabled_but_loopback_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_PORT", "8000")
    monkeypatch.delenv("SPLAT_REPLAY_FRONTEND_PORT", raising=False)
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.local_ipv4_addresses",
        lambda: ["192.168.10.20"],
    )
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.is_accessible_lan_endpoint",
        lambda _address, _port: True,
    )

    with TestClient(_build_app(enabled=True)) as client:
        response = client.get("/api/remote-access/status")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "active": False,
        "bind_host": "127.0.0.1",
        "port": 8000,
        "restart_required": True,
        "access_urls": [],
    }


def test_remote_access_status_reports_active_when_lan_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_PORT", "8000")
    monkeypatch.delenv("SPLAT_REPLAY_FRONTEND_PORT", raising=False)
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.local_ipv4_addresses",
        lambda: ["192.168.10.20"],
    )
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.is_accessible_lan_endpoint",
        lambda _address, _port: True,
    )

    with TestClient(_build_app(enabled=True)) as client:
        response = client.get("/api/remote-access/status")

    body: dict[str, Any] = response.json()
    assert body["active"] is True
    assert body["restart_required"] is False
    assert body["access_urls"] == ["http://192.168.10.20:8000/"]


def test_remote_access_status_uses_frontend_dev_port_for_access_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_PORT", "8000")
    monkeypatch.setenv("SPLAT_REPLAY_FRONTEND_PORT", "5173")
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.local_ipv4_addresses",
        lambda: ["192.168.10.20"],
    )
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.is_accessible_lan_endpoint",
        lambda _address, _port: True,
    )

    with TestClient(_build_app(enabled=True)) as client:
        response = client.get("/api/remote-access/status")

    body: dict[str, Any] = response.json()
    assert body["port"] == 5173
    assert body["access_urls"] == ["http://192.168.10.20:5173/"]


def test_remote_access_status_filters_out_unreachable_lan_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_PORT", "8000")
    monkeypatch.delenv("SPLAT_REPLAY_FRONTEND_PORT", raising=False)
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.local_ipv4_addresses",
        lambda: ["192.168.10.20", "172.30.112.1", "100.93.9.22"],
    )
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.is_accessible_lan_endpoint",
        lambda address, port: address == "192.168.10.20" and port == 8000,
    )

    with TestClient(_build_app(enabled=True)) as client:
        response = client.get("/api/remote-access/status")

    body: dict[str, Any] = response.json()
    assert body["access_urls"] == ["http://192.168.10.20:8000/"]
