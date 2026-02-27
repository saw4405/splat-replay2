"""Phase handler registry - フェーズハンドラの登録と実行。

Phase 4 Refactoring: Handler が Command を返すように変更し、UseCase で実行。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from splat_replay.application.interfaces import EventBusPort, LoggerPort
from splat_replay.application.services.recording.commands import (
    RecordingCommand,
)
from splat_replay.application.services.recording.ingame_handler import (
    InGamePhaseHandler,
)
from splat_replay.application.services.recording.matching_handler import (
    MatchingPhaseHandler,
)
from splat_replay.application.services.recording.paused_handler import (
    PausedStateHandler,
)
from splat_replay.application.services.recording.postfinish_handler import (
    PostFinishPhaseHandler,
)
from splat_replay.application.services.recording.result_handler import (
    ResultPhaseHandler,
)
from splat_replay.application.services.recording.standby_handler import (
    StandbyPhaseHandler,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
    SessionPhase,
)
from splat_replay.application.services.recording.weapon_detection_service import (
    WeaponDetectionService,
)
from splat_replay.domain.models import Frame
from splat_replay.domain.services import FrameAnalyzer, RecordState

if TYPE_CHECKING:
    pass


class PhaseHandlerRegistry:
    """フェーズハンドラの登録と実行を管理する。

    Strategy Pattern を使用して、各フェーズのロジックを分離。
    Handler は純粋関数的に Command を返し、副作用は UseCase で実行する。
    """

    def __init__(
        self,
        analyzer: FrameAnalyzer,
        logger: LoggerPort,
        event_bus: EventBusPort,
        weapon_detection_service: WeaponDetectionService,
    ):
        # フェーズハンドラの初期化
        self._standby = StandbyPhaseHandler(analyzer, logger, event_bus)
        self._matching = MatchingPhaseHandler(analyzer, logger, event_bus)
        self._in_game = InGamePhaseHandler(
            analyzer,
            logger,
            event_bus,
            weapon_detection_service,
        )
        self._post_finish = PostFinishPhaseHandler(analyzer, logger, event_bus)
        self._result = ResultPhaseHandler(analyzer, logger, event_bus)
        self._paused = PausedStateHandler(logger, event_bus)

        # フェーズ → ハンドラのマッピング
        self._handlers = {
            SessionPhase.STANDBY: self._standby,
            SessionPhase.MATCHING: self._matching,
            SessionPhase.IN_GAME: self._in_game,
            SessionPhase.POST_FINISH: self._post_finish,
            SessionPhase.RESULT: self._result,
        }

    async def handle_frame(
        self, frame: Frame, ctx: RecordingContext, state: RecordState
    ) -> RecordingCommand:
        """フレームを現在のフェーズに応じて処理する。

        Args:
            frame: 処理対象のフレーム
            ctx: 録画コンテキスト
            state: 現在の録画状態

        Returns:
            RecordingCommand: 実行すべきコマンドと更新されたコンテキスト
        """
        # PAUSED 状態は特別扱い（どのフェーズでも可能）
        if state is RecordState.PAUSED:
            return await self._paused.handle(frame, ctx, state)

        # 現在のフェーズを判定
        phase = ctx.phase(state)
        handler = self._handlers.get(phase)

        if handler is None:
            # 未知のフェーズ（通常は発生しない）
            return RecordingCommand.none(ctx)

        return await handler.handle(frame, ctx, state)

    def cancel_background_tasks(self) -> None:
        """バックグラウンドタスクを中断する。"""
        self._in_game.cancel_background_tasks()
