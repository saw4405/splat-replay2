from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    OBSSettingsView,
    RecorderStatus,
    VideoRecorderPort,
)
from splat_replay.domain.config import VideoStorageSettings
from splat_replay.infrastructure.adapters.obs.recorder_controller import (
    OBSRecorderController,
)
from splat_replay.infrastructure.adapters.video.replay_recorder_controller import (
    ReplayRecorderController,
)
from splat_replay.infrastructure.test_input import (
    resolve_configured_test_video,
)

StatusListener = Callable[[RecorderStatus], Awaitable[None]]


class AdaptiveVideoRecorder(VideoRecorderPort):
    """設定に応じて OBS とリプレイレコーダを切り替える。"""

    def __init__(
        self,
        settings: OBSSettingsView,
        storage_settings: VideoStorageSettings,
        logger: BoundLogger,
    ) -> None:
        self._logger = logger
        self._temp_output_dir = storage_settings.base_dir / "_replay_temp"
        self._obs_recorder = OBSRecorderController(settings, logger)
        self._obs_recorder.add_status_listener(self._forward_status)
        self._replay_recorder: ReplayRecorderController | None = None
        self._active_recorder: VideoRecorderPort = self._obs_recorder
        self._active_key = "live_capture"
        self._status_listeners: list[StatusListener] = []

    def update_settings(self, settings: OBSSettingsView) -> None:
        self._obs_recorder.update_settings(settings)

    def _resolve_recorder(self) -> tuple[str, VideoRecorderPort]:
        resolved = resolve_configured_test_video()
        if resolved is None:
            return "live_capture", self._obs_recorder

        key = str(resolved.selected_path)
        if self._replay_recorder is None or self._active_key != key:
            self._replay_recorder = ReplayRecorderController(
                input_video=resolved.selected_path,
                output_dir=self._temp_output_dir,
                logger=self._logger,
            )
            self._replay_recorder.add_status_listener(self._forward_status)
        return key, self._replay_recorder

    async def _select_recorder(self) -> VideoRecorderPort:
        key, recorder = self._resolve_recorder()
        if key != self._active_key or recorder is not self._active_recorder:
            await self._active_recorder.teardown()
            self._active_key = key
            self._active_recorder = recorder
        return self._active_recorder

    async def setup(self) -> None:
        recorder = await self._select_recorder()
        await recorder.setup()

    async def start(self) -> None:
        recorder = await self._select_recorder()
        await recorder.start()

    async def stop(self) -> Path | None:
        recorder = await self._select_recorder()
        return await recorder.stop()

    async def pause(self) -> None:
        recorder = await self._select_recorder()
        await recorder.pause()

    async def resume(self) -> None:
        recorder = await self._select_recorder()
        await recorder.resume()

    async def teardown(self) -> None:
        await self._active_recorder.teardown()

    async def _forward_status(self, status: RecorderStatus) -> None:
        for listener in list(self._status_listeners):
            await listener(status)

    def add_status_listener(self, listener: StatusListener) -> None:
        self._status_listeners.append(listener)

    def remove_status_listener(self, listener: StatusListener) -> None:
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)
