"""Switch動画保存通知の集約と録画コンテキストへの反映。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
from typing import cast

import numpy as np
import pytest

from splat_replay.application.services.recording.phase_handler_registry import (
    PhaseHandlerRegistry,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.domain.models import Frame, RecordingMetadata
from splat_replay.domain.services import FrameAnalyzer, RecordState
from splat_replay.domain.models.switch_capture import SwitchCaptureStatus


@pytest.fixture
def registry() -> PhaseHandlerRegistry:
    analyzer = Mock(spec=FrameAnalyzer)
    for method in (
        "detect_session_abort",
        "detect_session_finish",
        "detect_communication_error",
        "detect_session_judgement",
        "detect_loading",
    ):
        getattr(analyzer, method).return_value = False
    analyzer.detect_session_result.return_value = True
    weapon = Mock()

    async def process(
        *, frame: Frame, context: RecordingContext
    ) -> RecordingContext:
        return context

    weapon.process = process
    return PhaseHandlerRegistry(
        analyzer, Mock(), Mock(), weapon, clock=Mock(now=lambda: 200.0)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phase", ["in_game", "post_finish", "result", "paused"]
)
async def test_capture_times_survive_phase_handling_without_duplicates(
    registry: PhaseHandlerRegistry, phase: str
) -> None:
    frame = np.zeros((125, 575, 3), dtype=np.uint8)
    ctx = RecordingContext(
        battle_started_at=100.0,
        finish=phase == "post_finish",
        result_frame=frame if phase == "result" else None,
    )
    state = RecordState.PAUSED if phase == "paused" else RecordState.RECORDING
    statuses: list[SwitchCaptureStatus | None] = [
        "saving",
        "saving",
        None,
        "saving",
        "saved",
        "saved",
        "saving",
        None,
        None,
        "saving",
    ]
    cast(Mock, registry._analyzer).detect_switch_capture.side_effect = statuses
    for index in range(len(statuses)):
        command = await registry.handle_frame(
            frame, ctx, state, captured_at=101.25 + index
        )
        ctx = command.updated_context
    assert ctx.metadata.switch_capture_elapsed_seconds == (1.25, 7.25, 10.25)


@pytest.mark.asyncio
async def test_saved_only_and_frames_before_recording_do_not_invent_operation_time(
    registry: PhaseHandlerRegistry,
) -> None:
    frame = np.zeros((125, 575, 3), dtype=np.uint8)
    ctx = RecordingContext(battle_started_at=100.0)
    cast(
        Mock, registry._analyzer
    ).detect_switch_capture.return_value = "saving"
    command = await registry.handle_frame(
        frame, ctx, RecordState.RECORDING, captured_at=99.0
    )
    assert (
        command.updated_context.metadata.switch_capture_elapsed_seconds == ()
    )
    cast(Mock, registry._analyzer).detect_switch_capture.return_value = "saved"
    command = await registry.handle_frame(
        frame, ctx, RecordState.RECORDING, captured_at=110.0
    )
    assert (
        command.updated_context.metadata.switch_capture_elapsed_seconds == ()
    )
    cast(
        Mock, registry._analyzer
    ).detect_switch_capture.return_value = "saving"
    command = await registry.handle_frame(
        frame,
        command.updated_context,
        RecordState.RECORDING,
        captured_at=120.0,
    )
    assert command.updated_context.metadata.switch_capture_elapsed_seconds == (
        20.0,
    )
    fresh = await registry.handle_frame(
        frame,
        RecordingContext(battle_started_at=200.0),
        RecordState.RECORDING,
        captured_at=201.0,
    )
    assert fresh.updated_context.metadata.switch_capture_elapsed_seconds == (
        1.0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [RecordState.STOPPED, RecordState.PAUSED])
async def test_no_active_recording_does_not_store_notification(
    registry: PhaseHandlerRegistry,
    state: RecordState,
) -> None:
    frame = np.zeros((125, 575, 3), dtype=np.uint8)
    ctx = RecordingContext(result_frame=frame)
    cast(
        Mock, registry._analyzer
    ).detect_switch_capture.return_value = "saving"
    command = await registry.handle_frame(frame, ctx, state, captured_at=100.0)
    assert (
        command.updated_context.metadata.switch_capture_elapsed_seconds == ()
    )


def test_capture_times_merge_with_concurrent_metadata_edit() -> None:
    from splat_replay.application.services.recording.metadata_merger import (
        MetadataMerger,
    )
    from splat_replay.domain.models import Judgement

    base = RecordingMetadata()
    detected = replace(base, switch_capture_elapsed_seconds=(1.25,))
    manual = replace(base, judgement=Judgement.WIN)
    merged = MetadataMerger().merge_with_auto_update(
        base, detected, manual, frozenset({"judgement"})
    )
    assert merged.switch_capture_elapsed_seconds == (1.25,)
    assert merged.judgement is Judgement.WIN


@pytest.mark.asyncio
async def test_captured_image_reaches_recording_json_with_acquisition_time(
    registry: PhaseHandlerRegistry,
    tmp_path: Path,
) -> None:
    """取得→実画像照合→録画コンテキスト→JSONの内部連携を守る。"""
    import cv2
    import structlog
    from splat_replay.application.interfaces import CapturePort
    from splat_replay.application.services.recording.frame_capture_producer import (
        FrameCaptureProducer,
    )
    from splat_replay.application.services.recording.frame_processing_service import (
        FrameProcessingService,
    )
    from splat_replay.application.services.recording.recording_session_service import (
        RecordingSessionService,
    )
    from splat_replay.application.use_cases.auto_recording_use_case import (
        AutoRecordingUseCase,
    )
    from splat_replay.domain.config import ImageMatchingSettings
    from splat_replay.infrastructure.matchers.registry import MatcherRegistry
    from splat_replay.infrastructure.repositories.asset_file_operations import (
        AssetFileOperations,
    )

    backend = Path(__file__).resolve().parents[3]
    image = cv2.imread(
        str(backend / "tests/fixtures/templates/switch_capture_saving_1.png")
    )
    assert image is not None
    settings = ImageMatchingSettings.load_from_yaml(
        backend / "config/image_matching.yaml"
    )
    settings = ImageMatchingSettings(
        matchers={
            key: value
            for key, value in settings.matchers.items()
            if key.startswith("switch_capture_")
        }
    )
    detector = FrameAnalyzer(Mock(), Mock(), MatcherRegistry(settings))
    cast(
        Mock, registry._analyzer
    ).detect_switch_capture.side_effect = detector.detect_switch_capture
    frames = [image]
    capture = Mock(spec=CapturePort)
    capture.capture.side_effect = lambda: frames.pop() if frames else None
    clock = Mock(now=lambda: 125.5)
    producer = FrameCaptureProducer(capture, None, clock=clock)
    processor = FrameProcessingService(producer, registry._analyzer, Mock())
    producer.start()
    try:
        captured = await processor.acquire_captured_frame()
        assert captured is not None
    finally:
        producer.stop()
    session = Mock(spec=RecordingSessionService)
    session.state = RecordState.RECORDING
    use_case = AutoRecordingUseCase(
        session,
        processor,
        registry,
        RecordingContext(battle_started_at=100.0),
        capture,
        producer,
        Mock(),
        Mock(),
    )
    await use_case._process_armed_frame(captured.frame, captured.captured_at)
    operations = AssetFileOperations(structlog.get_logger())
    path = tmp_path / "battle.mp4"
    assert operations.save_metadata(path, use_case._context.metadata)
    loaded = operations.load_metadata(path)
    assert loaded is not None
    assert loaded.switch_capture_elapsed_seconds == (25.5,)
