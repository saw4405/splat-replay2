from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import SecretStr

from splat_replay.application.interfaces.data import (
    AudioInputHealthCheckResult,
)
from splat_replay.domain.config import OBSSettings
from splat_replay.infrastructure.adapters.obs.recorder_controller import (
    OBSRecorderController,
)
from splat_replay.infrastructure.adapters.obs.websocket_client import (
    InputVolumeMeterSample,
)


@dataclass(frozen=True)
class _CaptureDeviceSettingsStub:
    name: str


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
        self,
        meter_events: list[dict[str, object]] | None = None,
        *,
        inputs: list[dict[str, object]] | None = None,
        input_settings: dict[str, dict[str, object]] | None = None,
        property_items: dict[str, list[dict[str, object]]] | None = None,
        failed_requests: set[str] | None = None,
    ) -> None:
        self.is_connected = False
        self.requests: list[tuple[str, dict[str, object]]] = []
        self.meter_events = meter_events or []
        self.meter_checks: list[tuple[str, float]] = []
        self.inputs = inputs or [
            {"inputName": "MiraBox", "inputKind": "dshow_input"}
        ]
        self.input_settings = input_settings or {
            "MiraBox": {
                "video_device_id": "MiraBox Capture:\\\\?\\usb#vid",
                "last_video_device_id": "MiraBox Capture:\\\\?\\usb#vid",
            }
        }
        self.property_items = property_items or {}
        self.failed_requests = failed_requests or set()

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
        if request_type in self.failed_requests:
            raise RuntimeError(f"OBS request failed: {request_type}")
        if request_type == "GetInputList":
            return _OBSResponseStub({"inputs": self.inputs})
        if request_type == "GetInputSettings":
            input_name = str(data.get("inputName"))
            return _OBSResponseStub(
                {"inputSettings": self.input_settings.get(input_name, {})}
            )
        if request_type == "GetInputPropertiesListPropertyItems":
            input_name = str(data.get("inputName"))
            return _OBSResponseStub(
                {"propertyItems": self.property_items.get(input_name, [])}
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


class _ChangingSettingsWebSocketStub(_OBSWebSocketStub):
    def __init__(
        self, windows: list[dict[str, InputVolumeMeterSample]]
    ) -> None:
        super().__init__(
            inputs=[
                {
                    "inputName": "Mic",
                    "inputKind": "wasapi_input_capture",
                }
            ],
            input_settings={"Mic": {"device_id": "old"}},
        )
        self._windows = windows
        self.settings_reads = 0
        self.meter_windows_closed = False

    async def request(
        self,
        request_type: str,
        idempotent: bool = False,
        request_data: dict[str, object] | None = None,
    ) -> _OBSResponseStub:
        if request_type == "GetInputSettings":
            self.settings_reads += 1
            device_id = "old" if self.settings_reads == 1 else "new"
            return _OBSResponseStub(
                {"inputSettings": {"device_id": device_id}}
            )
        return await super().request(
            request_type,
            idempotent=idempotent,
            request_data=request_data,
        )

    async def iter_input_volume_meter_windows(
        self, *, window_seconds: float
    ) -> AsyncGenerator[dict[str, InputVolumeMeterSample], None]:
        _ = window_seconds
        try:
            for window in self._windows:
                yield window
        finally:
            self.meter_windows_closed = True


def _silent_result() -> AudioInputHealthCheckResult:
    return AudioInputHealthCheckResult(
        input_name="MiraBox Capture",
        status="silent",
        healthy=False,
        short_message="音量メーター未反応",
        details=(
            "OBS の入力「MiraBox Capture」の音量メーターが振れていません。"
            "録画は継続しますが、動画に音声が入らない可能性があります。"
        ),
        peak_db=None,
    )


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
async def test_obs_audio_health_keeps_exact_name_for_other_input_kinds() -> (
    None
):
    ws_client = _OBSWebSocketStub(
        meter_events=[
            {
                "inputName": "MiraBox Capture",
                "inputLevelsMul": [[0.04]],
                "inputLevelsDb": [[-28.0]],
            }
        ],
        inputs=[
            {
                "inputName": "MiraBox Capture",
                "inputKind": "wasapi_input_capture",
            }
        ],
    )
    controller = _OBSRecorderControllerMeterProbe(ws_client)

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.status == "ok"
    assert result.input_name == "MiraBox Capture"
    assert ws_client.meter_checks == [("MiraBox Capture", 0.1)]


@pytest.mark.asyncio
async def test_obs_audio_health_treats_input_list_failure_as_unknown() -> None:
    ws_client = _OBSWebSocketStub(failed_requests={"GetInputList"})
    controller = _OBSRecorderControllerMeterProbe(ws_client)

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.healthy is False
    assert result.status == "unknown"
    assert ws_client.meter_checks == []


@pytest.mark.asyncio
async def test_obs_audio_health_resolves_matching_coreaudio_device() -> None:
    device_id = "AppleUSBAudioEngine:MACROSILICON:MiraBox Capture:3100000:3"
    ws_client = _OBSWebSocketStub(
        meter_events=[
            {
                "inputName": "音声入力キャプチャ",
                "inputLevelsMul": [[0.04, 0.06]],
                "inputLevelsDb": [[-28.0, -24.0]],
            }
        ],
        inputs=[
            {"inputName": "MiraBox", "inputKind": "macos-avcapture"},
            {
                "inputName": "音声入力キャプチャ",
                "inputKind": "coreaudio_input_capture",
            },
            {"inputName": "別マイク", "inputKind": "coreaudio_input_capture"},
        ],
        input_settings={
            "MiraBox": {"device": "0x3100000534d2109"},
            "音声入力キャプチャ": {"device_id": device_id},
            "別マイク": {"device_id": "default"},
        },
        property_items={
            "音声入力キャプチャ": [
                {
                    "itemName": "MiraBox Capture",
                    "itemValue": device_id,
                    "itemEnabled": True,
                }
            ]
        },
    )
    controller = _OBSRecorderControllerMeterProbe(ws_client)

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.healthy is True
    assert result.status == "ok"
    assert result.input_name == "音声入力キャプチャ"
    assert ws_client.meter_checks == [("音声入力キャプチャ", 0.1)]
    assert (
        "GetInputPropertiesListPropertyItems",
        {
            "inputName": "音声入力キャプチャ",
            "propertyName": "device_id",
        },
    ) in ws_client.requests


@pytest.mark.asyncio
async def test_obs_audio_health_does_not_measure_macos_video_source() -> None:
    ws_client = _OBSWebSocketStub(
        inputs=[{"inputName": "MiraBox", "inputKind": "macos-avcapture"}],
        input_settings={"MiraBox": {"device_name": "MiraBox Capture"}},
    )
    controller = _OBSRecorderControllerMeterProbe(ws_client)

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.healthy is False
    assert result.status == "unknown"
    assert ws_client.meter_checks == []


@pytest.mark.asyncio
async def test_obs_audio_health_treats_ambiguous_coreaudio_devices_as_unknown() -> (
    None
):
    ws_client = _OBSWebSocketStub(
        inputs=[
            {"inputName": "音声1", "inputKind": "coreaudio_input_capture"},
            {"inputName": "音声2", "inputKind": "coreaudio_input_capture"},
        ],
        input_settings={
            "音声1": {"device_id": "device-id-1"},
            "音声2": {"device_id": "device-id-2"},
        },
        property_items={
            "音声1": [
                {
                    "itemName": "MiraBox Capture",
                    "itemValue": "device-id-1",
                    "itemEnabled": True,
                }
            ],
            "音声2": [
                {
                    "itemName": "MiraBox Capture",
                    "itemValue": "device-id-2",
                    "itemEnabled": True,
                }
            ],
        },
    )
    controller = _OBSRecorderControllerMeterProbe(ws_client)

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.healthy is False
    assert result.status == "unknown"
    assert ws_client.meter_checks == []


@pytest.mark.asyncio
async def test_obs_audio_health_treats_duplicate_coreaudio_device_names_as_unknown() -> (
    None
):
    ws_client = _OBSWebSocketStub(
        inputs=[
            {
                "inputName": "音声入力キャプチャ",
                "inputKind": "coreaudio_input_capture",
            }
        ],
        input_settings={"音声入力キャプチャ": {"device_id": "device-id-1"}},
        property_items={
            "音声入力キャプチャ": [
                {
                    "itemName": "MiraBox Capture",
                    "itemValue": "device-id-1",
                    "itemEnabled": True,
                },
                {
                    "itemName": "MiraBox Capture",
                    "itemValue": "device-id-2",
                    "itemEnabled": True,
                },
            ]
        },
    )
    controller = _OBSRecorderControllerMeterProbe(ws_client)

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.healthy is False
    assert result.status == "unknown"
    assert ws_client.meter_checks == []


@pytest.mark.asyncio
async def test_obs_audio_health_treats_coreaudio_device_lookup_failure_as_unknown() -> (
    None
):
    ws_client = _OBSWebSocketStub(
        inputs=[
            {
                "inputName": "音声入力キャプチャ",
                "inputKind": "coreaudio_input_capture",
            }
        ],
        input_settings={"音声入力キャプチャ": {"device_id": "device-id"}},
        failed_requests={"GetInputPropertiesListPropertyItems"},
    )
    controller = _OBSRecorderControllerMeterProbe(ws_client)

    result = await controller.check_audio_input_health(
        "MiraBox Capture", sample_duration_seconds=0.1
    )

    assert result.healthy is False
    assert result.status == "unknown"
    assert ws_client.meter_checks == []


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
    assert result.short_message == "音量メーター未反応"
    assert result.input_name == "MiraBox"
    assert result.peak_db == pytest.approx(-72.0)


@pytest.mark.asyncio
async def test_obs_audio_health_warns_when_meter_events_are_unavailable() -> (
    None
):
    controller = _OBSRecorderControllerMeterProbe(_OBSWebSocketStub())

    result = await controller.check_audio_input_health(
        "MiraBox", sample_duration_seconds=0.1
    )

    assert result.healthy is False
    assert result.status == "unknown"
    assert result.short_message == "音声確認失敗"
    assert "音量メーターイベントを取得できなかった" in result.details


@pytest.mark.asyncio
async def test_obs_audio_health_treats_empty_meter_levels_as_silent() -> None:
    controller = _OBSRecorderControllerMeterProbe(
        _OBSWebSocketStub(
            meter_events=[
                {
                    "inputName": "MiraBox",
                    "inputLevelsMul": [],
                }
            ]
        )
    )

    result = await controller.check_audio_input_health(
        "MiraBox", sample_duration_seconds=0.1
    )

    assert result.healthy is False
    assert result.status == "silent"
    assert result.short_message == "音量メーター未反応"


@pytest.mark.asyncio
async def test_observer_rechecks_input_assignment_and_closes_meter_stream() -> (
    None
):
    ws_client = _ChangingSettingsWebSocketStub(
        [
            {
                "Mic": InputVolumeMeterSample(
                    event_count=1,
                    numeric_mul_samples=1,
                    numeric_db_samples=1,
                    peak_mul=0.5,
                    peak_db=-6.0,
                )
            },
            {
                "Mic": InputVolumeMeterSample(
                    event_count=1,
                    numeric_mul_samples=0,
                    numeric_db_samples=0,
                    peak_mul=None,
                    peak_db=None,
                )
            },
        ]
    )
    controller = _OBSRecorderControllerMeterProbe(ws_client)
    observations = controller.observe_audio_input_health("Mic")

    stale_window = await asyncio.wait_for(anext(observations), timeout=0.5)
    current_window = await asyncio.wait_for(anext(observations), timeout=0.5)
    await asyncio.wait_for(observations.aclose(), timeout=2.0)

    assert stale_window.status == "unknown"
    assert current_window.status == "silent"
    assert ws_client.settings_reads == 3
    assert ws_client.meter_windows_closed is True
