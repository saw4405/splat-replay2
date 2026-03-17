from __future__ import annotations

import shutil
from pathlib import Path
from typing import Awaitable, Callable
from uuid import uuid4

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    OBSSettingsView,
    RecorderStatus,
    VideoRecorderPort,
)

StatusListener = Callable[[RecorderStatus], Awaitable[None]]


class ReplayRecorderController(VideoRecorderPort):
    """入力動画をそのまま録画結果として扱う E2E 用レコーダ。"""

    def __init__(
        self,
        input_video: Path,
        output_dir: Path,
        logger: BoundLogger,
    ) -> None:
        self._input_video = input_video
        self._output_dir = output_dir
        self._logger = logger
        self._status_listeners: list[StatusListener] = []
        self._state: RecorderStatus = "stopped"

    def update_settings(self, settings: OBSSettingsView) -> None:
        self._logger.debug(
            "ReplayRecorderController では OBS 設定更新を無視します"
        )

    async def setup(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._logger.info(
            "リプレイ録画コントローラを初期化しました",
            input_video=str(self._input_video),
            output_dir=str(self._output_dir),
        )

    async def start(self) -> None:
        if self._state == "started":
            return
        self._state = "started"
        await self._notify("started")

    async def stop(self) -> Path | None:
        if self._state == "stopped":
            return None
        output_path = self._output_dir / (
            f"replay-{uuid4().hex}{self._input_video.suffix}"
        )
        shutil.copy2(self._input_video, output_path)
        self._state = "stopped"
        await self._notify("stopped")
        self._logger.info(
            "入力動画を録画結果としてコピーしました",
            input_video=str(self._input_video),
            output_video=str(output_path),
        )
        return output_path

    async def pause(self) -> None:
        if self._state != "started":
            return
        self._state = "paused"
        await self._notify("paused")

    async def resume(self) -> None:
        if self._state != "paused":
            return
        self._state = "resumed"
        await self._notify("resumed")
        self._state = "started"

    async def teardown(self) -> None:
        self._state = "stopped"

    async def _notify(self, status: RecorderStatus) -> None:
        for listener in list(self._status_listeners):
            await listener(status)

    def add_status_listener(self, listener: StatusListener) -> None:
        self._status_listeners.append(listener)

    def remove_status_listener(self, listener: StatusListener) -> None:
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)
