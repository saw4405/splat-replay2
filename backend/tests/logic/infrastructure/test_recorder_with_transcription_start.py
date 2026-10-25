from __future__ import annotations

import asyncio
import threading
from typing import Any, cast

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    SpeechTranscriberPort,
    VideoAssetRepositoryPort,
    VideoRecorderPort,
)
from splat_replay.infrastructure.adapters.video.recorder_with_transcription import (
    RecorderWithTranscription,
)


class _LoggerStub:
    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        return None

    def error(self, event: str, **kw: object) -> None:
        return None


class _VideoRecorderStub:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._listeners: list[Any] = []

    async def setup(self) -> None:
        return None

    async def start(self) -> None:
        self._events.append("video")
        for listener in self._listeners:
            await listener("started")

    async def stop(self) -> None:
        for listener in self._listeners:
            await listener("stopped")
        return None

    def add_status_listener(self, listener: object) -> None:
        self._listeners.append(listener)


class _TranscriberStub:
    def __init__(
        self,
        events: list[str],
        *,
        ready: bool = True,
        start_error: Exception | None = None,
    ) -> None:
        self._events = events
        self._ready = ready
        self._start_error = start_error
        self.stop_calls = 0

    def start(self) -> None:
        self._events.append("transcription")
        if self._start_error is not None:
            raise self._start_error

    async def wait_until_ready(self, timeout_seconds: float) -> bool:
        assert timeout_seconds == 1.0
        self._events.append("microphone")
        return self._ready

    def stop(self) -> str:
        self.stop_calls += 1
        return ""


async def _record_state_change(events: list[str], status: str) -> None:
    assert status == "started"
    events.append("state")


def _recorder(
    video: _VideoRecorderStub,
    transcriber: _TranscriberStub | None,
    *,
    factory: Any = None,
) -> RecorderWithTranscription:
    return RecorderWithTranscription(
        recorder=cast(VideoRecorderPort, video),
        transcriber=cast(SpeechTranscriberPort | None, transcriber),
        asset_repo=cast(VideoAssetRepositoryPort, object()),
        logger=cast(BoundLogger, cast(Any, _LoggerStub())),
        transcriber_factory=factory,
    )


@pytest.mark.asyncio
async def test_transcriber_is_prepared_before_recording_hot_path() -> None:
    events: list[str] = []
    transcriber = _TranscriberStub(events)
    factory_calls = 0

    def factory() -> tuple[SpeechTranscriberPort, str]:
        nonlocal factory_calls
        factory_calls += 1
        return cast(SpeechTranscriberPort, transcriber), "settings-v1"

    recorder = _recorder(_VideoRecorderStub(events), None, factory=factory)
    recorder.add_status_listener(
        lambda status: _record_state_change(events, status)
    )

    await recorder.setup()
    await recorder.prepare_transcription()
    await recorder.start()

    assert factory_calls == 2
    assert events == ["video", "state", "transcription", "microphone"]


@pytest.mark.asyncio
async def test_recording_start_reads_latest_disabled_setting() -> None:
    events: list[str] = []
    factory_calls = 0

    def factory() -> tuple[None, str]:
        nonlocal factory_calls
        factory_calls += 1
        return None, "disabled"

    recorder = _recorder(_VideoRecorderStub(events), None, factory=factory)

    await recorder.start()

    assert factory_calls == 1
    assert events == ["video"]


@pytest.mark.asyncio
async def test_disabled_transcription_preparation_keeps_video_recording_available() -> (
    None
):
    events: list[str] = []
    factory_calls = 0

    def disabled_factory() -> tuple[None, str]:
        nonlocal factory_calls
        factory_calls += 1
        return None, "disabled"

    recorder = _recorder(
        _VideoRecorderStub(events), None, factory=disabled_factory
    )

    await recorder.prepare_transcription()
    await recorder.start()

    assert factory_calls == 2
    assert events == ["video"]


@pytest.mark.asyncio
async def test_transcription_preparation_during_recording_waits_until_next_start() -> (
    None
):
    events: list[str] = []
    transcriber = _TranscriberStub(events)
    selected: tuple[SpeechTranscriberPort | None, str] = (
        cast(SpeechTranscriberPort, transcriber),
        "enabled-v1",
    )
    factory_calls = 0

    def factory() -> tuple[SpeechTranscriberPort | None, str]:
        nonlocal factory_calls
        factory_calls += 1
        return selected

    video = _VideoRecorderStub(events)
    recorder = _recorder(video, None, factory=factory)

    await recorder.start()
    selected = (None, "disabled-v2")
    await recorder.prepare_transcription()
    await recorder.start()

    assert events == ["video", "transcription", "microphone"]
    assert factory_calls == 1
    assert transcriber.stop_calls == 0
    await recorder.stop()
    assert transcriber.stop_calls == 1
    await recorder.start()
    assert factory_calls == 2
    assert events == ["video", "transcription", "microphone", "video"]


@pytest.mark.asyncio
async def test_changed_setting_is_loaded_on_the_next_recording_start() -> None:
    events: list[str] = []
    transcriber = _TranscriberStub(events)
    selected: tuple[SpeechTranscriberPort | None, str] = (None, "disabled-v1")
    factory_calls = 0

    def factory() -> tuple[SpeechTranscriberPort | None, str]:
        nonlocal factory_calls
        factory_calls += 1
        return selected

    video = _VideoRecorderStub(events)
    recorder = _recorder(video, None, factory=factory)

    await recorder.start()
    selected = (cast(SpeechTranscriberPort, transcriber), "enabled-v2")
    await recorder.stop()
    await recorder.start()

    assert factory_calls == 2
    assert events == ["video", "video", "transcription", "microphone"]


@pytest.mark.asyncio
async def test_transcriber_retries_initialization_with_same_settings_fingerprint() -> (
    None
):
    events: list[str] = []
    transcriber = _TranscriberStub(events)
    selected: tuple[SpeechTranscriberPort | None, str] = (
        None,
        "same-settings",
    )

    def factory() -> tuple[SpeechTranscriberPort | None, str]:
        return selected

    recorder = _recorder(_VideoRecorderStub(events), None, factory=factory)

    await recorder.start()
    await recorder.stop()
    selected = (cast(SpeechTranscriberPort, transcriber), "same-settings")
    await recorder.start()

    assert events == ["video", "video", "transcription", "microphone"]


@pytest.mark.asyncio
async def test_armed_preparation_cannot_overwrite_settings_reloaded_at_start() -> (
    None
):
    events: list[str] = []
    armed_transcriber = _TranscriberStub(events)
    start_transcriber = _TranscriberStub(events)
    first_factory_started = threading.Event()
    release_first_factory = threading.Event()
    factory_calls = 0

    def factory() -> tuple[SpeechTranscriberPort, str]:
        nonlocal factory_calls
        factory_calls += 1
        if factory_calls == 1:
            first_factory_started.set()
            if not release_first_factory.wait(timeout=3):
                raise TimeoutError("テスト用の準備待機がタイムアウトしました")
            return cast(SpeechTranscriberPort, armed_transcriber), "armed-v1"
        return cast(SpeechTranscriberPort, start_transcriber), "started-v2"

    recorder = _recorder(_VideoRecorderStub(events), None, factory=factory)
    prepare_task = asyncio.create_task(recorder.prepare_transcription())
    assert await asyncio.to_thread(first_factory_started.wait, 1)

    start_task = asyncio.create_task(recorder.start())
    await asyncio.sleep(0)
    release_first_factory.set()
    await asyncio.gather(prepare_task, start_task)

    assert factory_calls == 2
    assert events == ["video", "transcription", "microphone"]
    assert armed_transcriber.stop_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ready", "start_error"),
    [
        (False, None),
        (True, RuntimeError("microphone unavailable")),
    ],
)
async def test_transcription_failure_does_not_stop_video_recording(
    ready: bool, start_error: Exception | None
) -> None:
    events: list[str] = []
    transcriber = _TranscriberStub(
        events, ready=ready, start_error=start_error
    )
    recorder = _recorder(_VideoRecorderStub(events), transcriber)

    await recorder.start()

    assert events[0] == "video"
    assert "transcription" in events
    assert transcriber.stop_calls == (1 if start_error else 0)
