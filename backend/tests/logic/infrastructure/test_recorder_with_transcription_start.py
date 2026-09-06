from __future__ import annotations

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

    assert factory_calls == 1
    assert events == ["video", "state", "transcription", "microphone"]


@pytest.mark.asyncio
async def test_recording_start_never_constructs_transcriber() -> None:
    events: list[str] = []
    factory_calls = 0

    def factory() -> tuple[None, str]:
        nonlocal factory_calls
        factory_calls += 1
        return None, "disabled"

    recorder = _recorder(_VideoRecorderStub(events), None, factory=factory)

    await recorder.start()

    assert factory_calls == 0
    assert events == ["video"]


@pytest.mark.asyncio
async def test_late_transcriber_preparation_joins_active_recording() -> None:
    events: list[str] = []
    transcriber = _TranscriberStub(events)

    def factory() -> tuple[SpeechTranscriberPort, str]:
        return cast(SpeechTranscriberPort, transcriber), "settings-v1"

    recorder = _recorder(_VideoRecorderStub(events), None, factory=factory)

    await recorder.start()
    await recorder.prepare_transcription()

    assert events == ["video", "transcription", "microphone"]


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
