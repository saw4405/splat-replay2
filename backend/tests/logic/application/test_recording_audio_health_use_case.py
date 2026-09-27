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
from splat_replay.application.services.recording.recording_audio_health import (
    RecordingAudioHealthService,
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
from splat_replay.domain.models import SwitchPowerState
from splat_replay.domain.services import RecordState, StateMachine


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
    def __init__(
        self,
        result: AudioInputHealthCheckResult
        | list[AudioInputHealthCheckResult],
        *,
        recovery: bool = False,
        start_error: Exception | None = None,
        cancel_error: Exception | None = None,
    ) -> None:
        self._results: list[AudioInputHealthCheckResult] = (
            result if isinstance(result, list) else [result]
        )
        self._recovery = recovery
        self._start_error = start_error
        self._cancel_error = cancel_error
        self.setup_called = False
        self.started = False
        self.audio_checks: list[str] = []
        self.sample_durations: list[float] = []
        self.recovery_calls = 0
        self.cancel_calls = 0
        self.status_listeners: list[object] = []

    def update_settings(self, settings: object) -> None:
        return None

    async def setup(self) -> None:
        self.setup_called = True

    async def start(self) -> None:
        if self._start_error is not None:
            raise self._start_error
        self.started = True

    async def prepare_transcription(self) -> None:
        return None

    async def cancel(self) -> None:
        self.cancel_calls += 1
        if self._cancel_error is not None:
            raise self._cancel_error

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
        self.sample_durations.append(sample_duration_seconds)
        if len(self._results) > 1:
            return self._results.pop(0)
        return self._results[0]

    async def try_recover_audio_input(self) -> bool:
        self.recovery_calls += 1
        return self._recovery

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


class _CaptureDeviceStub:
    def __init__(self, connected: bool | Exception) -> None:
        self.connected = connected
        self.checks = 0

    def is_connected(self) -> bool:
        self.checks += 1
        if isinstance(self.connected, Exception):
            raise self.connected
        return self.connected


def _audio_health_service(
    recorder: _RecorderSpy,
    *,
    power_state: SwitchPowerState | Exception,
    capture_connected: bool | Exception,
) -> tuple[RecordingAudioHealthService, _CaptureDeviceStub]:
    capture_device = _CaptureDeviceStub(capture_connected)

    def get_power_state() -> SwitchPowerState:
        if isinstance(power_state, Exception):
            raise power_state
        return power_state

    return (
        RecordingAudioHealthService(
            recorder=cast(VideoRecorderPort, recorder),
            capture_device=cast(Any, capture_device),
            config=cast(ConfigPort, _ConfigStub("MiraBox Capture")),
            power_state=get_power_state,
            logger=cast(Any, _LoggerStub()),
        ),
        capture_device,
    )


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


def _healthy_result() -> AudioInputHealthCheckResult:
    return AudioInputHealthCheckResult(
        input_name="MiraBox Capture",
        status="ok",
        healthy=True,
        short_message="",
        details="OBS 音声入力を確認しました。",
        peak_db=-12.0,
    )


def _muted_result() -> AudioInputHealthCheckResult:
    return AudioInputHealthCheckResult(
        input_name="MiraBox Capture",
        status="muted",
        healthy=False,
        short_message="音声ミュート",
        details="OBS 音声入力がミュートされています。",
        peak_db=None,
    )


@pytest.mark.asyncio
async def test_prepare_recording_only_sets_up_recorder() -> None:
    recorder = _RecorderSpy(_silent_result())
    service = RecordingPreparationService(
        recorder=cast(VideoRecorderPort, recorder),
        config=cast(ConfigPort, _ConfigStub("MiraBox Capture")),
        logger=cast(Any, _LoggerStub()),
    )

    await service.prepare_recording()

    assert recorder.setup_called is True
    assert recorder.audio_checks == []


@pytest.mark.asyncio
async def test_audio_recovery_restarts_after_confirmed_silence_and_rechecks() -> (
    None
):
    recorder = _RecorderSpy(
        [_silent_result(), _silent_result(), _healthy_result()],
        recovery=True,
    )
    service, capture_device = _audio_health_service(
        recorder,
        power_state=SwitchPowerState.ARMED,
        capture_connected=True,
    )

    result = await service.check_and_recover(sample_duration_seconds=0.35)

    assert result.healthy is True
    assert recorder.recovery_calls == 1
    assert recorder.sample_durations == [0.35, 1.0, 1.0]
    assert capture_device.checks == 1


@pytest.mark.asyncio
async def test_audio_readiness_checks_capture_before_switch_power() -> None:
    recorder = _RecorderSpy(_silent_result())
    capture_device = _CaptureDeviceStub(False)
    power_checks = 0

    def get_power_state() -> SwitchPowerState:
        nonlocal power_checks
        power_checks += 1
        return SwitchPowerState.ARMED

    service = RecordingAudioHealthService(
        recorder=cast(VideoRecorderPort, recorder),
        capture_device=cast(Any, capture_device),
        config=cast(ConfigPort, _ConfigStub("MiraBox Capture")),
        power_state=get_power_state,
        logger=cast(Any, _LoggerStub()),
    )

    result = await service.check_and_recover(sample_duration_seconds=0.35)

    assert result.status == "skipped"
    assert capture_device.checks == 1
    assert power_checks == 0
    assert recorder.audio_checks == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("power_state", "capture_connected"),
    [
        (SwitchPowerState.WAITING_FOR_POWER_ON, True),
        (RuntimeError("power check failed"), True),
        (SwitchPowerState.ARMED, False),
        (SwitchPowerState.ARMED, RuntimeError("device check failed")),
    ],
)
async def test_audio_recovery_skips_without_live_hardware_readiness(
    power_state: SwitchPowerState | Exception,
    capture_connected: bool | Exception,
) -> None:
    recorder = _RecorderSpy(_silent_result())
    service, capture_device = _audio_health_service(
        recorder,
        power_state=power_state,
        capture_connected=capture_connected,
    )

    result = await service.check_and_recover(sample_duration_seconds=0.35)

    assert result.status == "skipped"
    assert result.healthy is True
    assert recorder.recovery_calls == 0
    assert recorder.audio_checks == []
    assert capture_device.checks == 1


@pytest.mark.asyncio
async def test_audio_recovery_does_not_restart_for_configuration_warning() -> (
    None
):
    recorder = _RecorderSpy(_muted_result())
    service, capture_device = _audio_health_service(
        recorder,
        power_state=SwitchPowerState.ARMED,
        capture_connected=True,
    )

    result = await service.check_and_recover(sample_duration_seconds=0.35)

    assert result.status == "muted"
    assert recorder.recovery_calls == 0
    assert capture_device.checks == 1


@pytest.mark.asyncio
async def test_start_does_not_repeat_audio_health_check() -> None:
    state_machine = StateMachine()

    class _StateAwareRecorder(_RecorderSpy):
        async def start(self) -> None:
            assert state_machine.state is RecordState.RECORDING
            await super().start()

    recorder = _StateAwareRecorder(_silent_result())
    audio_health, _ = _audio_health_service(
        recorder,
        power_state=SwitchPowerState.ARMED,
        capture_connected=True,
    )
    publisher = _DomainPublisherSpy()
    service = RecordingSessionService(
        state_machine=state_machine,
        recorder=cast(RecorderWithTranscriptionPort, recorder),
        asset_repository=cast(
            VideoAssetRepositoryPort, _AssetRepositoryStub()
        ),
        analyzer=cast(Any, _AnalyzerStub()),
        logger=cast(Any, _LoggerStub()),
        context=RecordingContext(),
        domain_publisher=cast(Any, publisher),
        audio_health=audio_health,
    )

    await service.start()

    assert recorder.audio_checks == []
    assert recorder.started is True
    assert service.state is RecordState.RECORDING
    assert publisher.events == []


@pytest.mark.asyncio
async def test_start_failure_rolls_back_only_after_stop_confirmation() -> None:
    recorder = _RecorderSpy(
        _healthy_result(), start_error=RuntimeError("start failed")
    )
    service = RecordingSessionService(
        state_machine=StateMachine(),
        recorder=cast(RecorderWithTranscriptionPort, recorder),
        asset_repository=cast(
            VideoAssetRepositoryPort, _AssetRepositoryStub()
        ),
        analyzer=cast(Any, _AnalyzerStub()),
        logger=cast(Any, _LoggerStub()),
        context=RecordingContext(),
    )

    with pytest.raises(RuntimeError, match="start failed"):
        await service.start()

    assert recorder.cancel_calls == 1
    assert service.state is RecordState.STOPPED
    assert service.context.battle_started_at == 0.0


@pytest.mark.asyncio
async def test_start_failure_keeps_recording_when_status_is_unknown() -> None:
    recorder = _RecorderSpy(
        _healthy_result(),
        start_error=RuntimeError("start failed"),
        cancel_error=RuntimeError("status unavailable"),
    )
    service = RecordingSessionService(
        state_machine=StateMachine(),
        recorder=cast(RecorderWithTranscriptionPort, recorder),
        asset_repository=cast(
            VideoAssetRepositoryPort, _AssetRepositoryStub()
        ),
        analyzer=cast(Any, _AnalyzerStub()),
        logger=cast(Any, _LoggerStub()),
        context=RecordingContext(),
    )

    with pytest.raises(RuntimeError, match="start failed"):
        await service.start()

    assert recorder.cancel_calls == 1
    assert service.state is RecordState.RECORDING
    assert service.context.battle_started_at > 0.0
