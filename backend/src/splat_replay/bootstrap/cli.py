"""CLI composition root."""

from __future__ import annotations

import punq
from fastapi import FastAPI
from structlog.stdlib import BoundLogger
from typing import TYPE_CHECKING

from splat_replay.application.use_cases import AutoUseCase, UploadUseCase
from splat_replay.infrastructure.di import configure_container, resolve
from splat_replay.infrastructure.filesystem import PROJECT_ROOT
from splat_replay.interface.cli.main import CliDependencies, build_app

if TYPE_CHECKING:
    from splat_replay.interface.gui.webview_app import SplatReplayWebViewApp


class _LazyResources:
    def __init__(self) -> None:
        self._container: punq.Container | None = None
        self._logger: BoundLogger | None = None
        self._auto_use_case: AutoUseCase | None = None
        self._upload_use_case: UploadUseCase | None = None
        self._web_app: FastAPI | None = None

    def container(self) -> punq.Container:
        if self._container is None:
            self._container = configure_container()
        return self._container

    def logger(self) -> BoundLogger:
        if self._logger is None:
            self._logger = resolve(self.container(), BoundLogger)
        return self._logger

    def auto_use_case(self) -> AutoUseCase:
        if self._auto_use_case is None:
            self._auto_use_case = resolve(self.container(), AutoUseCase)
        return self._auto_use_case

    def upload_use_case(self) -> UploadUseCase:
        if self._upload_use_case is None:
            self._upload_use_case = resolve(self.container(), UploadUseCase)
        return self._upload_use_case

    def web_app(self) -> FastAPI:
        if self._web_app is None:
            from splat_replay.bootstrap.web_app import (
                create_app as create_web_app,
            )

            self._web_app = create_web_app(self.container())
        return self._web_app

    def webview_app(self) -> "SplatReplayWebViewApp":
        from splat_replay.interface.gui.webview_app import (
            SplatReplayWebViewApp,
        )

        return SplatReplayWebViewApp(
            project_root=PROJECT_ROOT,
            logger=self.logger(),
            backend_app_module="splat_replay.bootstrap.web_app:app",
        )

    def start_dev_server(self) -> None:
        from splat_replay.bootstrap.dev_server import start_dev_server

        start_dev_server()


_resources = _LazyResources()

dependencies = CliDependencies(
    auto_use_case=_resources.auto_use_case,
    upload_use_case=_resources.upload_use_case,
    logger=_resources.logger,
    web_app=_resources.web_app,
    webview_app=_resources.webview_app,
    start_dev_server=_resources.start_dev_server,
)

app = build_app(dependencies)

__all__ = ["app"]
