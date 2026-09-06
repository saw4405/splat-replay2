from __future__ import annotations

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


class _RecoveryProcessStub(_RunningProcessStub):
    def __init__(self, restarted: bool) -> None:
        self.restarted = restarted
        self.restart_calls = 0

    async def restart_for_recovery(self) -> bool:
        self.restart_calls += 1
        return self.restarted


class _RecoveryWebSocketStub:
    def __init__(self) -> None:
        self.is_connected = True
        self.disconnect_calls = 0
        self.connect_calls = 0

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.is_connected = False

    async def connect(self) -> None:
        self.connect_calls += 1
        self.is_connected = True


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


class _OBSRecorderControllerRecoveryProbe(OBSRecorderController):
    def __init__(
        self,
        *,
        record_active: bool,
        process_manager: _RecoveryProcessStub,
        ws_client: _RecoveryWebSocketStub,
    ) -> None:
        super().__init__(
            OBSSettings(websocket_password=SecretStr("")),
            cast(Any, _LoggerStub()),
        )
        self._record_active = record_active
        self._process_manager = cast(Any, process_manager)
        self._ws_client = cast(Any, ws_client)
        self.setup_calls = 0

    async def _get_record_status(self) -> tuple[bool, bool]:
        return self._record_active, False

    async def setup(self) -> None:
        self.setup_calls += 1


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


@pytest.mark.asyncio
async def test_obs_audio_health_treats_empty_meter_levels_as_silence() -> None:
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


@pytest.mark.asyncio
async def test_obs_audio_recovery_restarts_matching_idle_process() -> None:
    process_manager = _RecoveryProcessStub(restarted=True)
    ws_client = _RecoveryWebSocketStub()
    controller = _OBSRecorderControllerRecoveryProbe(
        record_active=False,
        process_manager=process_manager,
        ws_client=ws_client,
    )

    restarted = await controller.try_recover_audio_input()

    assert restarted is True
    assert process_manager.restart_calls == 1
    assert ws_client.disconnect_calls == 1
    assert controller.setup_calls == 1


@pytest.mark.asyncio
async def test_obs_audio_recovery_never_restarts_while_recording() -> None:
    process_manager = _RecoveryProcessStub(restarted=True)
    ws_client = _RecoveryWebSocketStub()
    controller = _OBSRecorderControllerRecoveryProbe(
        record_active=True,
        process_manager=process_manager,
        ws_client=ws_client,
    )

    restarted = await controller.try_recover_audio_input()

    assert restarted is False
    assert process_manager.restart_calls == 0
    assert ws_client.disconnect_calls == 0


@pytest.mark.asyncio
async def test_obs_audio_recovery_preserves_external_process() -> None:
    process_manager = _RecoveryProcessStub(restarted=False)
    ws_client = _RecoveryWebSocketStub()
    controller = _OBSRecorderControllerRecoveryProbe(
        record_active=False,
        process_manager=process_manager,
        ws_client=ws_client,
    )

    restarted = await controller.try_recover_audio_input()

    assert restarted is False
    assert process_manager.restart_calls == 1
    assert ws_client.disconnect_calls == 1
    assert ws_client.connect_calls == 1
    assert controller.setup_calls == 0
