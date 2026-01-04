"""DI Container: Main configuration and resolver.

Phase 3 リファクタリング - DI コンテナのメイン設定。
モジュール別に分割された登録関数を統合。
"""

from __future__ import annotations

from typing import TypeVar

import punq
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    ConfigPort,
    EnvironmentPort,
    FileSystemPort,
    LoggerPort,
    PathsPort,
)
from splat_replay.application.services import AutoRecorder
from splat_replay.application.services.common.queries import AssetQueryService
from splat_replay.domain.config import AppSettings
from splat_replay.domain.services import StateMachine
from splat_replay.infrastructure.adapters.system.cross_cutting import (
    FileSystemPathsAdapter,
    LocalFileSystemAdapter,
    ProcessEnvironmentAdapter,
    StructlogLoggerAdapter,
    TomlConfigAdapter,
)
from splat_replay.infrastructure.di.adapters import register_adapters
from splat_replay.infrastructure.di.app_services import register_app_services
from splat_replay.infrastructure.di.config import (
    register_config,
    register_image_matching_settings,
)
from splat_replay.infrastructure.di.domain_services import (
    register_domain_services,
)
from splat_replay.infrastructure.di.use_cases import register_app_usecases
from splat_replay.infrastructure.logging import get_logger
from splat_replay.infrastructure.runtime import AppRuntime

T = TypeVar("T")


def configure_container() -> punq.Container:
    """アプリで利用する依存関係を登録する。"""
    container = punq.Container()

    # Cross-cutting concerns（横断的関心事）の登録
    logger_adapter = StructlogLoggerAdapter()
    container.register(LoggerPort, instance=logger_adapter)

    config_adapter = TomlConfigAdapter()
    container.register(ConfigPort, instance=config_adapter)

    paths_adapter = FileSystemPathsAdapter()
    container.register(PathsPort, instance=paths_adapter)

    file_system_adapter = LocalFileSystemAdapter()
    container.register(FileSystemPort, instance=file_system_adapter)

    environment_adapter = ProcessEnvironmentAdapter()
    container.register(EnvironmentPort, instance=environment_adapter)

    # インフラ実装で利用する BoundLogger を登録
    logger = get_logger()
    container.register(BoundLogger, instance=logger)

    state_machine = StateMachine()
    container.register(StateMachine, instance=state_machine)

    # Runtime (async loop & buses)
    runtime = AppRuntime()
    runtime.start()
    container.register(AppRuntime, instance=runtime)

    app_settings = register_config(container)
    container.register(AppSettings, instance=app_settings)
    register_image_matching_settings(container)
    register_adapters(container)
    register_domain_services(container)
    register_app_services(container)
    register_app_usecases(container)

    try:
        ar = resolve(container, AutoRecorder)
        container.register(AutoRecorder, instance=ar)

        rt = resolve(container, AppRuntime)
        handlers = ar.command_handlers()
        for name, handler in handlers.items():
            rt.command_bus.register(name, handler)
    except Exception:
        pass

    # Register asset query commands
    try:
        aq = resolve(container, AssetQueryService)
        rt = resolve(container, AppRuntime)
        for name, handler in aq.command_handlers().items():
            rt.command_bus.register(name, handler)
    except Exception:
        pass

    return container


def resolve(container: punq.Container, cls: type[T]) -> T:
    """DI コンテナから依存を解決する"""
    return container.resolve(cls)


__all__ = ["configure_container", "resolve"]
