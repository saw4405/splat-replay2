"""UploadPort の DI 登録テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock
from typing import TypeVar, cast

import punq
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    AuthenticatedClientPort,
    EnvironmentPort,
    UploadPort,
)
from splat_replay.domain.models import SetupState
from splat_replay.domain.repositories import SetupStateRepository
from splat_replay.infrastructure.adapters.upload import (
    NoOpUploadPort,
    YouTubeClient,
)
from splat_replay.infrastructure.di import adapters as di_adapters
from splat_replay.infrastructure.di.adapters import register_adapters

ServiceT = TypeVar("ServiceT")


class _StubEnvironment:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._values.get(name, default)

    def set(self, name: str, value: str) -> None:
        self._values[name] = value


class _RegistrationContainer:
    def __init__(self, environment: _StubEnvironment) -> None:
        self._container = punq.Container()
        self._container.register(BoundLogger, instance=MagicMock())
        self._container.register(EnvironmentPort, instance=environment)
        self._registering = True

    def register(self, *args: object, **kwargs: object) -> object:
        return self._container.register(*args, **kwargs)

    def resolve(
        self, service_key: type[ServiceT], **kwargs: object
    ) -> ServiceT:
        if self._registering:
            if service_key in {
                BoundLogger,
                EnvironmentPort,
            }:
                return cast(
                    ServiceT, self._container.resolve(service_key, **kwargs)
                )
            return cast(ServiceT, MagicMock())

        return cast(ServiceT, self._container.resolve(service_key, **kwargs))


def _build_container(environment: _StubEnvironment) -> _RegistrationContainer:
    container = _RegistrationContainer(environment)
    register_adapters(cast(punq.Container, container))
    container._registering = False
    return container


def test_register_adapters_uses_noop_upload_port_when_flag_enabled() -> None:
    container = _build_container(
        _StubEnvironment({"SPLAT_REPLAY_E2E_NOOP_UPLOAD": "1"})
    )

    uploader = container.resolve(UploadPort)

    assert isinstance(uploader, NoOpUploadPort)


def test_register_adapters_keeps_youtube_client_when_flag_disabled() -> None:
    container = _build_container(_StubEnvironment({}))

    uploader = container.resolve(UploadPort)

    assert isinstance(uploader, YouTubeClient)


def test_authenticated_client_port_still_uses_youtube_client() -> None:
    container = _build_container(
        _StubEnvironment({"SPLAT_REPLAY_E2E_NOOP_UPLOAD": "1"})
    )

    client = container.resolve(AuthenticatedClientPort)

    assert isinstance(client, YouTubeClient)


def test_setup_state_repository_uses_settings_directory(
    monkeypatch, tmp_path
) -> None:
    settings_file = tmp_path / "sandbox" / "settings.toml"
    unrelated_config_dir = tmp_path / "runtime-config"

    monkeypatch.setattr(di_adapters.paths, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(di_adapters.paths, "CONFIG_DIR", unrelated_config_dir)

    container = _build_container(_StubEnvironment({}))

    repository = container.resolve(SetupStateRepository)
    repository.save_installation_state(
        SetupState(is_completed=True, youtube_permission_dialog_shown=True)
    )

    assert (settings_file.parent / "installation_state.toml").exists()
    assert not (unrelated_config_dir / "installation_state.toml").exists()
