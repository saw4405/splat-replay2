from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest

from splat_replay.interface.web.routers.remote_access import (
    _non_public_profile_aliases_from_json,
    is_accessible_lan_endpoint,
    local_ipv4_addresses,
)


def test_accessible_lan_endpoint_allows_slow_first_local_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Socket:
        def __enter__(self) -> "_Socket":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_create_connection(
        _address: tuple[str, int],
        timeout: float,
    ) -> _Socket:
        if timeout < 1.0:
            raise TimeoutError
        return _Socket()

    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.socket.create_connection",
        fake_create_connection,
    )

    assert is_accessible_lan_endpoint("192.168.10.20", 5173) is True


def test_non_public_profile_aliases_accepts_windows_enum_numbers() -> None:
    raw_json = (
        "["
        '{"InterfaceAlias":"Wi-Fi","NetworkCategory":1},'
        '{"InterfaceAlias":"Guest","NetworkCategory":0},'
        '{"InterfaceAlias":"Domain","NetworkCategory":2}'
        "]"
    )

    assert _non_public_profile_aliases_from_json(raw_json) == {
        "Wi-Fi",
        "Domain",
    }


def test_local_ipv4_addresses_uses_only_non_public_physical_lan_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.non_public_network_interface_aliases",
        lambda: {"Wi-Fi"},
    )
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.psutil.net_if_stats",
        lambda: {
            "Wi-Fi": SimpleNamespace(isup=True),
            "Tailscale": SimpleNamespace(isup=True),
            "vEthernet (WSL (Hyper-V firewall))": SimpleNamespace(isup=True),
        },
    )
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.psutil.net_if_addrs",
        lambda: {
            "Wi-Fi": [
                SimpleNamespace(
                    family=socket.AF_INET,
                    address="192.168.1.32",
                )
            ],
            "Tailscale": [
                SimpleNamespace(
                    family=socket.AF_INET,
                    address="100.93.9.22",
                )
            ],
            "vEthernet (WSL (Hyper-V firewall))": [
                SimpleNamespace(
                    family=socket.AF_INET,
                    address="172.30.112.1",
                )
            ],
        },
    )

    assert local_ipv4_addresses() == ["192.168.1.32"]


def test_local_ipv4_addresses_returns_empty_when_only_public_lan_adapter_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.non_public_network_interface_aliases",
        lambda: set(),
    )
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.psutil.net_if_stats",
        lambda: {"Wi-Fi": SimpleNamespace(isup=True)},
    )
    monkeypatch.setattr(
        "splat_replay.interface.web.routers.remote_access.psutil.net_if_addrs",
        lambda: {
            "Wi-Fi": [
                SimpleNamespace(
                    family=socket.AF_INET,
                    address="192.168.1.32",
                )
            ],
        },
    )

    assert local_ipv4_addresses() == []
