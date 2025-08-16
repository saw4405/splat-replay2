import asyncio
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    RecorderStatus,
    RecorderWithTranscriptionPort,
    SpeechTranscriberPort,
    VideoAssetRepository,
    VideoRecorderPort,
)


class RecorderWithTranscription(RecorderWithTranscriptionPort):
    """動画・文字起こしの録画を制御するサービス。"""

    def __init__(
        self,
        recorder: VideoRecorderPort,
        transcriber: Optional[SpeechTranscriberPort],
        asset_repo: VideoAssetRepository,
        logger: BoundLogger,
    ) -> None:
        self.recorder = recorder
        self.transcriber = transcriber
        self.asset_repo = asset_repo
        self.logger = logger
        self._status_listeners: List[
            Callable[[RecorderStatus], Awaitable[None]]
        ] = []

    async def init(self) -> None:
        await self.recorder.init()
        self.recorder.add_status_listener(self._notify_status_change)

    async def start(self):
        await self.recorder.start()
        if self.transcriber is not None:
            self.transcriber.start()

    async def stop(self) -> Tuple[Optional[Path], Optional[Path]]:
        video_path = await self.recorder.stop()
        srt_path = None
        if self.transcriber is not None:
            subtitle = self.transcriber.stop()
            if video_path:
                srt_path = video_path.parent / f"{video_path.stem}.srt"
                await asyncio.to_thread(
                    srt_path.write_text, subtitle, encoding="utf-8"
                )
        return video_path, srt_path

    async def cancel(self):
        await self.recorder.stop()
        if self.transcriber is not None:
            self.transcriber.stop()

    async def pause(self):
        await self.recorder.pause()
        if self.transcriber is not None:
            self.transcriber.pause()

    async def resume(self):
        await self.recorder.resume()
        if self.transcriber is not None:
            self.transcriber.resume()

    async def close(self) -> None:
        self.recorder.remove_status_listener(self._notify_status_change)
        await self.recorder.close()

    async def _notify_status_change(self, status: RecorderStatus) -> None:
        """録画状態変化をリスナーに通知する。"""
        for listener in self._status_listeners:
            await listener(status)

    def add_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None:
        """録画状態変化リスナーを登録する。"""
        self._status_listeners.append(listener)

    def remove_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None:
        """録画状態変化リスナーを解除する。"""
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)
