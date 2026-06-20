from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from splat_replay.application.interfaces import (
    ConfigPort,
    RecorderWithTranscriptionPort,
    VideoAssetRepositoryPort,
    VideoRecorderPort,
)
from splat_replay.application.interfaces.data import (
    AudioInputHealthCheckResult,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.recording_preparation import (
    RecordingPreparationService,
)
from splat_replay.application.services.recording.recording_session_service import (
    RecordingSessionService,
)
from splat_replay.domain.events import RecordingAudioHealthChecked
from splat_replay.domain.services import RecordState, StateMachine


@dataclass(frozen=True)
class _CaptureDeviceSettingsStub:
    name: str
    hardware_id: str | None = None
    location_path: str | None = None
    parent_instance_id: str | None = None


class _ConfigStub:
    def __init__(self, capture_device_name: str) -> None:
        self._capture_device_name = capture_device_name

    def get_capture_device_settings(self) -> _CaptureDeviceSettingsStub:
        return _CaptureDeviceSettingsStub(name=self._capture_device_name)


class _LoggerStub:
    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        return None

    def error(self, event: str, **kw: object) -> None:
        return None


class _DomainPublisherSpy:
    def __init__(self) -> None:
        self.events: list[object] = []

    def publish_domain_event(self, event: object) -> None:
        self.events.append(event)


class _RecorderSpy:
    def __init__(self, result: AudioInputHealthCheckResult) -> None:
        self._result = result
        self.setup_called = False
        self.started = False
        self.audio_checks: list[str] = []
        self.status_listeners: list[object] = []

    def update_settings(self, settings: object) -> None:
        return None

    async def setup(self) -> None:
        self.setup_called = True

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> Path | None:
        return None

    async def pause(self) -> None:
        return None

    async def resume(self) -> None:
        return None

    async def teardown(self) -> None:
        return None

    async def check_audio_input_health(
        self, input_name: str, *, sample_duration_seconds: float
    ) -> AudioInputHealthCheckResult:
        self.audio_checks.append(input_name)
        return self._result

    def add_status_listener(self, listener: object) -> None:
        self.status_listeners.append(listener)

    def remove_status_listener(self, listener: object) -> None:
        if listener in self.status_listeners:
            self.status_listeners.remove(listener)


class _AssetRepositoryStub:
    def save_recording(self, **kwargs: object) -> object:
        return object()


class _AnalyzerStub:
    async def extract_session_result(
        self, frame: object, game_mode: object
    ) -> None:
        return None


def _silent_result() -> AudioInputHealthCheckResult:
    return AudioInputHealthCheckResult(
        input_name="MiraBox Capture",
        status="silent",
        healthy=False,
        short_message="音声入力なし",
        details=(
            "OBS の入力「MiraBox Capture」の音量メーターが振れていません。"
            "録画は継続しますが、動画に音声が入らない可能性があります。"
        ),
        peak_db=None,
    )


@pytest.mark.asyncio
async def test_prepare_recording_checks_audio_health_after_obs_setup() -> None:
    recorder = _RecorderSpy(_silent_result())
    service = RecordingPreparationService(
        recorder=cast(VideoRecorderPort, recorder),
        config=cast(ConfigPort, _ConfigStub("MiraBox Capture")),
        logger=cast(Any, _LoggerStub()),
    )

    result = await service.prepare_recording()

    assert recorder.setup_called is True
    assert recorder.audio_checks == ["MiraBox Capture"]
    assert result == _silent_result()


@pytest.mark.asyncio
async def test_start_warns_on_audio_health_failure_without_blocking() -> None:
    recorder = _RecorderSpy(_silent_result())
    publisher = _DomainPublisherSpy()
    service = RecordingSessionService(
        state_machine=StateMachine(),
        recorder=cast(RecorderWithTranscriptionPort, recorder),
        asset_repository=cast(
            VideoAssetRepositoryPort, _AssetRepositoryStub()
        ),
        analyzer=cast(Any, _AnalyzerStub()),
        logger=cast(Any, _LoggerStub()),
        context=RecordingContext(),
        domain_publisher=cast(Any, publisher),
        config=cast(ConfigPort, _ConfigStub("MiraBox Capture")),
    )

    await service.start()

    assert recorder.audio_checks == ["MiraBox Capture"]
    assert recorder.started is True
    assert service.state is RecordState.RECORDING
    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert isinstance(event, RecordingAudioHealthChecked)
    assert event.input_name == "MiraBox Capture"
    assert event.healthy is False
    assert event.status == "silent"
    assert event.short_message == "音声入力なし"
