from __future__ import annotations

import asyncio
import time
from typing import Any, cast

import pytest

from splat_replay.application.interfaces import (
    CapturePort,
    LoggerPort,
    RecorderWithTranscriptionPort,
    VideoAssetRepositoryPort,
)
from splat_replay.application.services.recording.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.application.services.recording.frame_processing_service import (
    FrameProcessingService,
)
from splat_replay.application.services.recording.phase_handler_registry import (
    PhaseHandlerRegistry,
)
from splat_replay.application.services.recording.publisher_worker import (
    PublisherWorker,
)
from splat_replay.application.services.recording.recording_audio_health import (
    RecordingAudioHealthService,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.recording_session_service import (
    RecordingSessionService,
)
from splat_replay.application.use_cases.auto_recording_use_case import (
    AutoRecordingUseCase,
)
from splat_replay.domain.models import SwitchPowerMonitor, SwitchPowerState
from splat_replay.domain.services import StateMachine


class _RecorderStub:
    def add_status_listener(self, listener: object) -> None:
        return None

    async def start(self) -> None:
        await asyncio.sleep(0)

    async def prepare_transcription(self) -> None:
        await asyncio.sleep(1.1)


class _SlowAudioHealthStub:
    async def check_and_recover(
        self, *, sample_duration_seconds: float
    ) -> None:
        await asyncio.sleep(1.1)


class _LoggerStub:
    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        return None

    def error(self, event: str, **kw: object) -> None:
        return None


@pytest.mark.perf
@pytest.mark.asyncio
async def test_recording_start_hot_path_does_not_wait_for_audio_health() -> (
    None
):
    service = RecordingSessionService(
        state_machine=StateMachine(),
        recorder=cast(RecorderWithTranscriptionPort, _RecorderStub()),
        asset_repository=cast(VideoAssetRepositoryPort, object()),
        analyzer=cast(Any, object()),
        logger=cast(Any, _LoggerStub()),
        context=RecordingContext(),
        audio_health=cast(RecordingAudioHealthService, _SlowAudioHealthStub()),
    )
    use_case = AutoRecordingUseCase(
        session_service=service,
        frame_processor=cast(FrameProcessingService, object()),
        phase_handlers=cast(PhaseHandlerRegistry, object()),
        context=RecordingContext(),
        capture=cast(CapturePort, object()),
        capture_producer=cast(FrameCaptureProducer, object()),
        publisher_worker=cast(PublisherWorker, object()),
        logger=cast(LoggerPort, _LoggerStub()),
    )
    use_case._power_monitor = SwitchPowerMonitor(state=SwitchPowerState.ARMED)

    started_at = time.perf_counter()
    await use_case._refresh_audio_health_for_power_state()
    await service.start()
    elapsed = time.perf_counter() - started_at
    await use_case._cancel_audio_preparation()

    # バトル開始後のアプリ内処理予算。OBS自体の応答時間は実機で別計測する。
    assert elapsed < 1.0
