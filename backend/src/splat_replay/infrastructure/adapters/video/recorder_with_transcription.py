import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    AudioInputHealthCheckResult,
    RecorderStatus,
    RecorderWithTranscriptionPort,
    SpeechTranscriberPort,
    VideoAssetRepositoryPort,
    VideoRecorderPort,
)


class RecorderWithTranscription(RecorderWithTranscriptionPort):
    """動画・文字起こしの録画を制御するサービス。"""

    TRANSCRIPTION_START_TIMEOUT_SECONDS = 1.0

    def __init__(
        self,
        recorder: VideoRecorderPort,
        transcriber: Optional[SpeechTranscriberPort],
        asset_repo: VideoAssetRepositoryPort,
        logger: BoundLogger,
        transcriber_factory: Callable[
            [], tuple[Optional[SpeechTranscriberPort], str]
        ]
        | None = None,
    ) -> None:
        self.recorder = recorder
        self.transcriber = transcriber
        self.asset_repo = asset_repo
        self.logger = logger
        self._transcriber_factory = transcriber_factory
        self._transcriber_fingerprint: str | None = None
        self._recording_started = False
        self._recording_starting = False
        self._transcriber_started = False
        self._transcription_settings_lock = asyncio.Lock()
        self._status_listeners: List[
            Callable[[RecorderStatus], Awaitable[None]]
        ] = []

    async def setup(self) -> None:
        await self.recorder.setup()
        self.recorder.add_status_listener(self._notify_status_change)

    async def prepare_transcription(self) -> None:
        """録画開始を待たせないよう、文字起こしを事前構築する。"""
        async with self._transcription_settings_lock:
            # ARMED後の準備が録画開始後に遅れて完了しても、進行中の録画へ
            # 設定を適用しない。実際の開始時には最新設定を再読込する。
            if self._recording_started or self._recording_starting:
                return
            await self._reload_transcription_settings()

    async def _reload_transcription_settings(self) -> None:
        if self._transcriber_factory is None:
            return
        try:
            transcriber, fingerprint = await asyncio.to_thread(
                self._transcriber_factory
            )
        except Exception as exc:
            self.logger.error(
                "文字起こし設定の再読み込みに失敗しました",
                error_type=type(exc).__name__,
            )
            self.transcriber = None
            self._transcriber_fingerprint = None
            return
        if fingerprint != self._transcriber_fingerprint or (
            self.transcriber is None and transcriber is not None
        ):
            self.transcriber = transcriber
            self._transcriber_fingerprint = fingerprint

    async def start(self) -> None:
        async with self._transcription_settings_lock:
            if self._recording_started or self._recording_starting:
                self.logger.warning("録画開始をスキップします（既に開始済み）")
                return
            self._recording_starting = True
            try:
                await self._reload_transcription_settings()
                await self.recorder.start()
                self._recording_started = True
                await self._start_transcription()
            finally:
                self._recording_starting = False

    async def _start_transcription(self) -> None:
        if self.transcriber is None or self._transcriber_started:
            return
        try:
            self.transcriber.start()
            self._transcriber_started = True
            ready = await self.transcriber.wait_until_ready(
                self.TRANSCRIPTION_START_TIMEOUT_SECONDS
            )
            if not ready:
                self.logger.warning(
                    "文字起こしのマイク入力を1秒以内に開始できませんでした。映像録画は継続します。"
                )
        except Exception as exc:
            self.logger.warning(
                "文字起こしを開始できませんでした。映像録画は継続します。",
                error_type=type(exc).__name__,
            )
            with suppress(Exception):
                self.transcriber.stop()
            self._transcriber_started = False

    async def stop(self) -> Tuple[Optional[Path], Optional[Path]]:
        async with self._transcription_settings_lock:
            video_path = await self.recorder.stop()
            self._recording_started = False
            subtitle: str | None = None
            if self.transcriber is not None and self._transcriber_started:
                try:
                    subtitle = self.transcriber.stop()
                finally:
                    self._transcriber_started = False
        srt_path = None
        if video_path and subtitle is not None:
            srt_path = video_path.parent / f"{video_path.stem}.srt"
            await asyncio.to_thread(
                srt_path.write_text, subtitle, encoding="utf-8"
            )
        return video_path, srt_path

    async def cancel(self) -> None:
        async with self._transcription_settings_lock:
            video_path = await self.recorder.stop()
            self._recording_started = False
            if self.transcriber is not None and self._transcriber_started:
                try:
                    self.transcriber.stop()
                finally:
                    self._transcriber_started = False
        if video_path is None:
            self.logger.warning(
                "録画中止時に削除対象ファイルを取得できませんでした"
            )
            return
        deleted = self.asset_repo.delete_recording(video_path)
        if deleted:
            self.logger.info(
                "録画中止で生成されたファイルを削除しました",
                video_path=str(video_path),
            )
            return
        self.logger.warning(
            "録画中止で生成されたファイルの削除が完了しませんでした",
            video_path=str(video_path),
        )

    async def pause(self) -> None:
        await self.recorder.pause()
        if self.transcriber is not None and self._transcriber_started:
            self.transcriber.pause()

    async def resume(self) -> None:
        await self.recorder.resume()
        if self.transcriber is not None and self._transcriber_started:
            self.transcriber.resume()

    async def teardown(self) -> None:
        self.recorder.remove_status_listener(self._notify_status_change)
        await self.recorder.teardown()

    async def check_audio_input_health(
        self, input_name: str, *, sample_duration_seconds: float
    ) -> AudioInputHealthCheckResult:
        return await self.recorder.check_audio_input_health(
            input_name,
            sample_duration_seconds=sample_duration_seconds,
        )

    async def observe_audio_input_health(
        self, input_name: str
    ) -> AsyncGenerator[AudioInputHealthCheckResult, None]:
        observations = self.recorder.observe_audio_input_health(input_name)
        try:
            async for result in observations:
                yield result
        finally:
            await observations.aclose()

    async def _notify_status_change(self, status: RecorderStatus) -> None:
        """録画状態変化をリスナーに通知する。"""
        for listener in self._status_listeners:
            await listener(status)
        if status == "started":
            self._recording_started = True
            await self._start_transcription()
        elif status == "stopped":
            self._recording_started = False

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
