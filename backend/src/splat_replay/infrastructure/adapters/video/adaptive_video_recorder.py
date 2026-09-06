from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    AudioInputHealthCheckResult,
    OBSSettingsView,
    RecorderStatus,
    VideoRecorderPort,
)
from splat_replay.domain.config import VideoStorageSettings
from splat_replay.infrastructure.adapters.video.replay_recorder_controller import (
    ReplayRecorderController,
)
from splat_replay.infrastructure.test_input import (
    resolve_configured_test_video,
)

StatusListener = Callable[[RecorderStatus], Awaitable[None]]
LiveRecorderFactory = Callable[
    [OBSSettingsView, BoundLogger], VideoRecorderPort
]


def _build_live_recorder(
    settings: OBSSettingsView,
    logger: BoundLogger,
) -> VideoRecorderPort:
    """実機用 OBS レコーダーを必要になった時点で生成する。"""
    from splat_replay.infrastructure.adapters.obs.recorder_controller import (
        OBSRecorderController,
    )

    return OBSRecorderController(settings, logger)


class AdaptiveVideoRecorder(VideoRecorderPort):
    """設定に応じて OBS とリプレイレコーダを切り替える。"""

    def __init__(
        self,
        settings: OBSSettingsView,
        storage_settings: VideoStorageSettings,
        logger: BoundLogger,
        *,
        live_recorder_factory: LiveRecorderFactory
        | None = _build_live_recorder,
    ) -> None:
        self._logger = logger
        self._settings = settings
        self._temp_output_dir = storage_settings.base_dir / "_replay_temp"
        self._live_recorder_factory = live_recorder_factory
        self._live_recorder: VideoRecorderPort | None = None
        self._replay_recorder: ReplayRecorderController | None = None
        self._replay_key: str | None = None
        self._active_recorder: VideoRecorderPort | None = None
        self._active_key: str | None = None
        self._status_listeners: list[StatusListener] = []

    def update_settings(self, settings: OBSSettingsView) -> None:
        self._settings = settings
        if self._live_recorder is not None:
            self._live_recorder.update_settings(settings)

    def _resolve_live_recorder(self) -> VideoRecorderPort:
        if self._live_recorder is not None:
            return self._live_recorder
        if self._live_recorder_factory is None:
            raise RuntimeError(
                "リプレイ実行では OBS レコーダーへフォールバックできません"
            )
        self._live_recorder = self._live_recorder_factory(
            self._settings, self._logger
        )
        self._live_recorder.add_status_listener(self._forward_status)
        return self._live_recorder

    def _resolve_recorder(self) -> tuple[str, VideoRecorderPort]:
        resolved = resolve_configured_test_video()
        if resolved is None:
            return "live_capture", self._resolve_live_recorder()

        key = str(resolved.selected_path)
        if self._replay_recorder is None or self._replay_key != key:
            self._replay_recorder = ReplayRecorderController(
                input_video=resolved.selected_path,
                output_dir=self._temp_output_dir,
                logger=self._logger,
            )
            self._replay_recorder.add_status_listener(self._forward_status)
            self._replay_key = key
        return key, self._replay_recorder

    async def _select_recorder(self) -> VideoRecorderPort:
        key, recorder = self._resolve_recorder()
        if key != self._active_key or recorder is not self._active_recorder:
            if self._active_recorder is not None:
                await self._active_recorder.teardown()
            self._active_key = key
            self._active_recorder = recorder
        if self._active_recorder is None:
            raise RuntimeError("有効な VideoRecorderPort がありません")
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
        if self._active_recorder is not None:
            await self._active_recorder.teardown()

    async def check_audio_input_health(
        self, input_name: str, *, sample_duration_seconds: float
    ) -> AudioInputHealthCheckResult:
        recorder = await self._select_recorder()
        return await recorder.check_audio_input_health(
            input_name,
            sample_duration_seconds=sample_duration_seconds,
        )

    async def try_recover_audio_input(self) -> bool:
        recorder = await self._select_recorder()
        return await recorder.try_recover_audio_input()

    async def _forward_status(self, status: RecorderStatus) -> None:
        for listener in list(self._status_listeners):
            await listener(status)

    def add_status_listener(self, listener: StatusListener) -> None:
        self._status_listeners.append(listener)

    def remove_status_listener(self, listener: StatusListener) -> None:
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)
