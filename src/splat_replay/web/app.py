"""ASGI application entry point for uvicorn."""

from __future__ import annotations

from splat_replay.application.services import (
    AutoRecorder,
    DeviceChecker,
    RecordingPreparationService,
    SettingsService,
)
from splat_replay.application.use_cases import UploadUseCase
from splat_replay.infrastructure.adapters import GuiRuntimePortAdapter
from splat_replay.infrastructure.runtime.runtime import AppRuntime
from splat_replay.shared.di import configure_container, resolve
from splat_replay.shared.logger import get_logger
from splat_replay.web.server import WebServer

# Initialize DI container
container = configure_container()

# Resolve dependencies
auto_recorder = resolve(container, AutoRecorder)
device_checker = resolve(container, DeviceChecker)
recording_preparation_service = resolve(container, RecordingPreparationService)
runtime_adapter = resolve(container, GuiRuntimePortAdapter)
settings_service = resolve(container, SettingsService)
app_runtime = resolve(container, AppRuntime)
upload_use_case = resolve(container, UploadUseCase)
logger = get_logger()

# Create web server
web_server = WebServer(
    auto_recorder=auto_recorder,
    device_checker=device_checker,
    recording_preparation_service=recording_preparation_service,
    command_dispatcher=runtime_adapter,  # CommandDispatcher
    logger=logger,
    settings_service=settings_service,
    event_bus=app_runtime.event_bus,
    upload_use_case=upload_use_case,
)

# Export app for uvicorn
app = web_server.app

__all__ = ["app"]
