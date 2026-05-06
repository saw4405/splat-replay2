"""LAN remote access status endpoints."""

from __future__ import annotations

import ipaddress
import json
import os
import platform
import socket
import subprocess
from typing import TYPE_CHECKING

import psutil
from fastapi import APIRouter
from pydantic import BaseModel

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


LAN_BIND_HOSTS = {"0.0.0.0", "::", "::0"}
LAN_ENDPOINT_CHECK_TIMEOUT_SECONDS = 1.0
WINDOWS_NETWORK_PROFILE_TIMEOUT_SECONDS = 2.0
HOUSEHOLD_LAN_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
VIRTUAL_INTERFACE_NAME_PATTERNS = (
    "bluetooth",
    "hyper-v",
    "loopback",
    "npcap",
    "pseudo",
    "tailscale",
    "tap",
    "tunnel",
    "vethernet",
    "virtual",
    "virtualbox",
    "vmware",
    "wsl",
    "zerotier",
)


class RemoteAccessStatusResponse(BaseModel):
    enabled: bool
    active: bool
    bind_host: str
    port: int
    restart_required: bool
    access_urls: list[str]


def is_lan_bind_host(host: str) -> bool:
    return host.strip().lower() in LAN_BIND_HOSTS


def _is_candidate_ipv4(address: str) -> bool:
    if address.startswith("127.") or address.startswith("169.254."):
        return False
    return address not in {"0.0.0.0", ""}


def _is_household_lan_ipv4(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False

    return (
        parsed.version == 4
        and _is_candidate_ipv4(address)
        and any(parsed in network for network in HOUSEHOLD_LAN_NETWORKS)
    )


def _is_physical_lan_interface_name(name: str) -> bool:
    normalized = name.casefold()
    return not any(
        pattern in normalized for pattern in VIRTUAL_INTERFACE_NAME_PATTERNS
    )


def _non_public_profile_aliases_from_json(raw_json: str) -> set[str]:
    parsed = json.loads(raw_json)
    items = parsed if isinstance(parsed, list) else [parsed]
    result: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        alias = item.get("InterfaceAlias")
        category = item.get("NetworkCategory")
        if not isinstance(alias, str):
            continue
        if _is_non_public_network_category(category):
            result.add(alias)
    return result


def _is_non_public_network_category(category: object) -> bool:
    if isinstance(category, str):
        normalized = category.strip()
        if normalized.isdigit():
            return int(normalized) != 0
        return normalized.casefold() != "public"

    if type(category) is int:
        return category != 0

    return False


def non_public_network_interface_aliases() -> set[str] | None:
    if platform.system() != "Windows":
        return None

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                (
                    "Get-NetConnectionProfile | "
                    "Select-Object InterfaceAlias,NetworkCategory | "
                    "ConvertTo-Json -Compress"
                ),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=WINDOWS_NETWORK_PROFILE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        return _non_public_profile_aliases_from_json(result.stdout)
    except json.JSONDecodeError:
        return None


def local_ipv4_addresses() -> list[str]:
    """Return likely household LAN IPv4 addresses for the current PC."""
    try:
        interface_addrs = psutil.net_if_addrs()
        interface_stats = psutil.net_if_stats()
    except OSError:
        return []

    non_public_aliases = non_public_network_interface_aliases()
    result: list[str] = []
    seen: set[str] = set()
    for interface_name, addresses in interface_addrs.items():
        stats = interface_stats.get(interface_name)
        if stats is None or not stats.isup:
            continue
        if not _is_physical_lan_interface_name(interface_name):
            continue
        if (
            non_public_aliases is not None
            and interface_name not in non_public_aliases
        ):
            continue
        for item in addresses:
            if item.family != socket.AF_INET:
                continue
            address = str(item.address)
            if address in seen or not _is_household_lan_ipv4(address):
                continue
            seen.add(address)
            result.append(address)
    return result


def _current_bind_host() -> str:
    return os.environ.get("SPLAT_REPLAY_BACKEND_BIND_HOST", "127.0.0.1")


def _env_port(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _current_backend_port() -> int:
    return _env_port("SPLAT_REPLAY_BACKEND_PORT", 8000)


def _current_access_port() -> int:
    return _env_port("SPLAT_REPLAY_FRONTEND_PORT", _current_backend_port())


def is_accessible_lan_endpoint(address: str, port: int) -> bool:
    try:
        with socket.create_connection(
            (address, port),
            timeout=LAN_ENDPOINT_CHECK_TIMEOUT_SECONDS,
        ):
            return True
    except OSError:
        return False


def _build_access_urls(port: int) -> list[str]:
    return [
        f"http://{address}:{port}/"
        for address in local_ipv4_addresses()
        if is_accessible_lan_endpoint(address, port)
    ]


def create_remote_access_router(server: "WebAPIServer") -> APIRouter:
    router = APIRouter(prefix="/api/remote-access", tags=["remote_access"])

    @router.get("/status", response_model=RemoteAccessStatusResponse)
    async def get_remote_access_status() -> RemoteAccessStatusResponse:
        enabled = server.settings_service.fetch_remote_access_enabled()
        bind_host = _current_bind_host()
        port = _current_access_port()
        lan_bound = is_lan_bind_host(bind_host)

        return RemoteAccessStatusResponse(
            enabled=enabled,
            active=enabled and lan_bound,
            bind_host=bind_host,
            port=port,
            restart_required=enabled != lan_bound,
            access_urls=_build_access_urls(port)
            if enabled and lan_bound
            else [],
        )

    return router


__all__ = [
    "RemoteAccessStatusResponse",
    "create_remote_access_router",
    "is_accessible_lan_endpoint",
    "is_lan_bind_host",
    "local_ipv4_addresses",
    "non_public_network_interface_aliases",
]
