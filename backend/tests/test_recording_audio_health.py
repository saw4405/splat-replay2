from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import SecretStr

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
from splat_replay.domain.config import OBSSettings
from splat_replay.domain.services import RecordState, StateMachine
from splat_replay.infrastructure.adapters.obs.recorder_controller import (
    OBSRecorderController,
)


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


@dataclass(frozen=True)
class _OBSResponseStub:
    res_data: dict[str, object] | None


class _RunningProcessStub:
    async def is_running(self) -> bool:
        return True


class _OBSWebSocketStub:
    def __init__(
        self, meter_events: list[dict[str, object]] | None = None
    ) -> None:
        self.is_connected = False
        self.requests: list[tuple[str, dict[str, object]]] = []
        self.meter_events = meter_events or []
        self.meter_checks: list[tuple[str, float]] = []

    async def connect(self) -> None:
        self.is_connected = True

    async def request(
        self,
        request_type: str,
        idempotent: bool = False,
        request_data: dict[str, object] | None = None,
    ) -> _OBSResponseStub:
        data = request_data or {}
        self.requests.append((request_type, data))
        if request_type == "GetInputList":
            return _OBSResponseStub(
                {
                    "inputs": [
                        {
                            "inputName": "MiraBox",
                            "inputKind": "dshow_input",
                        }
                    ]
                }
            )
        if request_type == "GetInputSettings":
            return _OBSResponseStub(
                {
                    "inputKind": "dshow_input",
                    "inputSettings": {
                        "video_device_id": "MiraBox Capture:\\\\?\\usb#vid",
                        "last_video_device_id": (
                            "MiraBox Capture:\\\\?\\usb#vid"
                        ),
                    },
                }
            )
        if request_type == "GetInputMute":
            return _OBSResponseStub({"inputMuted": False})
        if request_type == "GetInputAudioTracks":
            return _OBSResponseStub(
                {"inputAudioTracks": {"1": True, "2": True}}
            )
        if request_type == "GetSourceActive":
            return _OBSResponseStub(
                {"videoActive": True, "videoShowing": True}
            )
        raise AssertionError(f"Unexpected OBS request: {request_type}")

    async def set_event_subscriptions(self, subscriptions: int) -> None:
        return None

    async def subscribe_default_events(self) -> None:
        return None

    async def collect_input_volume_meter_events(
        self, input_name: str, *, sample_duration_seconds: float
    ) -> list[dict[str, object]]:
        self.meter_checks.append((input_name, sample_duration_seconds))
        return self.meter_events


class _OBSRecorderControllerProbe(OBSRecorderController):
    def __init__(
        self,
        ws_client: _OBSWebSocketStub,
        sample: tuple[float, float | None] | None,
    ) -> None:
        super().__init__(
            OBSSettings(websocket_password=SecretStr("")),
            cast(Any, _LoggerStub()),
        )
        self._process_manager = cast(Any, _RunningProcessStub())
        self._ws_client = cast(Any, ws_client)
        self._sample = sample

    async def _sample_audio_meter(
        self, input_name: str, *, sample_duration_seconds: float
    ) -> tuple[float, float | None] | None:
        return self._sample


class _OBSRecorderControllerMeterProbe(OBSRecorderController):
    def __init__(self, ws_client: _OBSWebSocketStub) -> None:
        super().__init__(
            OBSSettings(websocket_password=SecretStr("")),
            cast(Any, _LoggerStub()),
        )
        self._process_manager = cast(Any, _RunningProcessStub())
        self._ws_client = cast(Any, ws_client)


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


@pytest.mark.asyncio
async def test_obs_audio_health_resolves_dshow_input_by_device_name() -> None:
    ws_client = _OBSWebSocketStub()
    controller = _OBSRecorderControllerProbe(ws_client, sample=(0.42, -7.0))

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.healthy is True
    assert result.status == "ok"
    assert result.input_name == "MiraBox"
    assert ("GetInputSettings", {"inputName": "MiraBox"}) in ws_client.requests
    assert ("GetInputMute", {"inputName": "MiraBox"}) in ws_client.requests


@pytest.mark.asyncio
async def test_obs_audio_health_samples_dedicated_obs_meter() -> None:
    ws_client = _OBSWebSocketStub(
        meter_events=[
            {
                "inputName": "MiraBox",
                "inputLevelsMul": [[0.0012, 0.0033, 0.0033]],
                "inputLevelsDb": [[-58.4, -49.6, -49.6]],
            }
        ],
    )
    controller = _OBSRecorderControllerMeterProbe(ws_client)

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.healthy is True
    assert result.status == "ok"
    assert result.input_name == "MiraBox"
    assert result.peak_db == pytest.approx(-49.6)
    assert ws_client.meter_checks == [("MiraBox", 0.1)]


@pytest.mark.asyncio
async def test_obs_audio_health_warns_when_meter_stays_silent() -> None:
    ws_client = _OBSWebSocketStub(
        meter_events=[
            {
                "inputName": "MiraBox",
                "inputLevelsMul": [[0.0, 0.0002, 0.0002]],
                "inputLevelsDb": [[-96.0, -72.0, -72.0]],
            }
        ],
    )
    controller = _OBSRecorderControllerMeterProbe(ws_client)

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.healthy is False
    assert result.status == "silent"
    assert result.short_message == "音声入力なし"
    assert result.input_name == "MiraBox"
    assert result.peak_db == pytest.approx(-72.0)


@pytest.mark.asyncio
async def test_obs_audio_health_warns_when_meter_events_are_unavailable() -> (
    None
):
    controller = _OBSRecorderControllerProbe(_OBSWebSocketStub(), sample=None)

    result = await controller.check_audio_input_health(
        "MiraBox", sample_duration_seconds=0.1
    )

    assert result.healthy is False
    assert result.status == "unknown"
    assert result.short_message == "音声確認失敗"
    assert "音量メーターイベントを取得できなかった" in result.details
