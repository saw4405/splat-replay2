from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    VideoAssetRepositoryPort,
    VideoRecorderPort,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.recording_session_service import (
    RecordingSessionService,
)
from splat_replay.domain.models import GameMode, RecordingMetadata
from splat_replay.domain.services import RecordEvent, RecordState, StateMachine
from splat_replay.infrastructure.adapters.video.recorder_with_transcription import (
    RecorderWithTranscription,
)


class _DummyLogger:
    def debug(self, *args: object, **kwargs: object) -> None:
        return None

    def info(self, *args: object, **kwargs: object) -> None:
        return None

    def warning(self, *args: object, **kwargs: object) -> None:
        return None

    def error(self, *args: object, **kwargs: object) -> None:
        return None


class _StateMachineStub:
    def __init__(self) -> None:
        self.state = RecordState.RECORDING
        self.events: list[RecordEvent] = []

    def add_listener(self, listener: object) -> None:
        _ = listener

    async def handle(self, event: RecordEvent) -> None:
        self.events.append(event)
        if event is RecordEvent.STOP:
            self.state = RecordState.STOPPED


class _RecorderStub:
    def __init__(self, stopped_video_path: Path) -> None:
        self._stopped_video_path = stopped_video_path
        self.status_listeners: list[object] = []

    def update_settings(self, settings: object) -> None:
        _ = settings

    async def setup(self) -> None:
        return None

    async def start(self) -> None:
        return None

    async def stop(self) -> Path | None:
        return self._stopped_video_path

    async def pause(self) -> None:
        return None

    async def resume(self) -> None:
        return None

    async def teardown(self) -> None:
        return None

    def add_status_listener(self, listener: object) -> None:
        self.status_listeners.append(listener)

    def remove_status_listener(self, listener: object) -> None:
        if listener in self.status_listeners:
            self.status_listeners.remove(listener)


class _AssetRepositoryStub:
    def __init__(self) -> None:
        self.deleted_paths: list[Path] = []

    def delete_recording(self, video: Path) -> bool:
        self.deleted_paths.append(video)
        video.unlink(missing_ok=True)
        return not video.exists()


class _AnalyzerStub:
    async def extract_session_result(
        self, frame: object, game_mode: object
    ) -> None:
        _ = frame, game_mode
        return None


@pytest.mark.asyncio
async def test_cancel_deletes_temporary_recording_and_resets_metadata(
    tmp_path: Path,
) -> None:
    stopped_video_path = tmp_path / "capture.mp4"
    stopped_video_path.write_bytes(b"temporary-recording")
    asset_repository = _AssetRepositoryStub()
    state_machine = _StateMachineStub()
    recorder = RecorderWithTranscription(
        recorder=cast(
            VideoRecorderPort,
            _RecorderStub(stopped_video_path),
        ),
        transcriber=None,
        asset_repo=cast(VideoAssetRepositoryPort, asset_repository),
        logger=cast(BoundLogger, cast(Any, _DummyLogger())),
    )
    service = RecordingSessionService(
        state_machine=cast(StateMachine, state_machine),
        recorder=recorder,
        asset_repository=cast(VideoAssetRepositoryPort, asset_repository),
        analyzer=cast(Any, _AnalyzerStub()),
        logger=cast(BoundLogger, cast(Any, _DummyLogger())),
        context=RecordingContext(
            metadata=RecordingMetadata(
                game_mode=GameMode.BATTLE,
                started_at=datetime(2026, 3, 24, 22, 0, 0),
            ),
            battle_started_at=123.0,
        ),
    )

    await service.cancel()

    assert state_machine.events == [RecordEvent.STOP]
    assert asset_repository.deleted_paths == [stopped_video_path]
    assert stopped_video_path.exists() is False
    assert service.state is RecordState.STOPPED
    assert service.context.battle_started_at == 0.0
    assert service.context.metadata.game_mode is GameMode.BATTLE
    assert service.context.metadata.started_at is None
