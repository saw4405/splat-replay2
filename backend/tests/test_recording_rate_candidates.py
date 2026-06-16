from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pytest

from splat_replay.application.interfaces import (
    LoggerPort,
    RecorderWithTranscriptionPort,
    VideoAssetRepositoryPort,
)
from splat_replay.application.services.recording.recording_context import (
    MatchRateCandidate,
    RecordingContext,
)
from splat_replay.application.services.recording.recording_session_service import (
    RecordingSessionService,
)
from splat_replay.domain.models import (
    BattleResult,
    Frame,
    GameMode,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
    Udemae,
    VideoAsset,
    XP,
    as_frame,
)
from splat_replay.domain.services import (
    FrameAnalyzer,
    RecordState,
    StateMachine,
)


class _Logger:
    def debug(self, event: str, **kw: object) -> None:
        _ = event, kw

    def info(self, event: str, **kw: object) -> None:
        _ = event, kw

    def warning(self, event: str, **kw: object) -> None:
        _ = event, kw

    def error(self, event: str, **kw: object) -> None:
        _ = event, kw

    def exception(self, event: str, **kw: object) -> None:
        _ = event, kw


class _StateMachine:
    state = RecordState.RECORDING

    def add_listener(self, listener: object) -> None:
        _ = listener

    async def handle(self, event: object) -> None:
        _ = event
        self.state = RecordState.STOPPED


class _Recorder:
    def add_status_listener(self, listener: object) -> None:
        _ = listener


class _AssetRepository:
    def save_recording(
        self,
        video: Path,
        srt: Path | None,
        screenshot: object,
        metadata: RecordingMetadata,
    ) -> VideoAsset:
        _ = srt, screenshot
        return VideoAsset(video=video, metadata=metadata)


class _Analyzer:
    def __init__(self, result: BattleResult) -> None:
        self._result = result

    async def extract_session_result(
        self, frame: Frame, game_mode: GameMode
    ) -> BattleResult:
        _ = frame, game_mode
        return self._result


def _frame() -> Frame:
    return as_frame(np.zeros((2, 2, 3), dtype=np.uint8))


def _result(match: Match) -> BattleResult:
    return BattleResult(
        match=match,
        rule=Rule.RAINMAKER,
        stage=Stage.HAMMERHEAD_BRIDGE,
        kill=7,
        death=5,
        special=2,
    )


def _service(
    context: RecordingContext, result: BattleResult
) -> RecordingSessionService:
    return RecordingSessionService(
        state_machine=cast(StateMachine, _StateMachine()),
        recorder=cast(RecorderWithTranscriptionPort, _Recorder()),
        asset_repository=cast(VideoAssetRepositoryPort, _AssetRepository()),
        analyzer=cast(FrameAnalyzer, _Analyzer(result)),
        logger=cast(LoggerPort, _Logger()),
        context=context,
    )


@pytest.mark.parametrize(
    ("final_match", "expected_rate"),
    [
        (Match.X, XP(2219.8)),
        (Match.ANARCHY_OPEN, Udemae("S+")),
        (Match.ANARCHY_SERIES, Udemae("S+")),
    ],
)
@pytest.mark.asyncio
async def test_result_applies_rate_candidate_for_confirmed_match(
    final_match: Match, expected_rate: XP | Udemae
) -> None:
    context = RecordingContext(
        metadata=RecordingMetadata(game_mode=GameMode.BATTLE),
        result_frame=_frame(),
        rate_candidates=(
            MatchRateCandidate(Match.X, XP(2219.8)),
            MatchRateCandidate(Match.ANARCHY, Udemae("S+")),
        ),
    )
    service = _service(context, _result(final_match))

    await service._extract_and_apply_result()

    assert service.context.metadata.rate == expected_rate


@pytest.mark.asyncio
async def test_reset_clears_rate_candidates_with_metadata() -> None:
    context = RecordingContext(
        metadata=RecordingMetadata(game_mode=GameMode.BATTLE),
        rate_candidates=(MatchRateCandidate(Match.X, XP(2219.8)),),
    )
    service = _service(context, _result(Match.X))

    await service.reset()

    assert service.context.metadata.rate is None
    assert service.context.rate_candidates == ()
