"""Matching phase handler - マッチング中の処理。

Phase 4 Refactoring: Handler を純粋関数化し、副作用ではなく Command を返す。
"""

from __future__ import annotations

from splat_replay.application.interfaces import EventBusPort, LoggerPort
from splat_replay.application.services.recording.commands import (
    RecordingCommand,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.domain.events import BattleStarted, ScheduleChanged
from splat_replay.domain.models import Frame
from splat_replay.domain.services import FrameAnalyzer, RecordState


class MatchingPhaseHandler:
    """MATCHING フェーズ（マッチング中）の処理。

    責務:
    - スケジュール変更検出
    - バトル開始検出
    - 検出結果に応じた Command を返す（副作用は UseCase で実行）
    """

    def __init__(
        self,
        analyzer: FrameAnalyzer,
        logger: LoggerPort,
        event_bus: EventBusPort,
    ):
        self.analyzer = analyzer
        self.logger = logger
        self.event_bus = event_bus

    async def handle(
        self, frame: Frame, ctx: RecordingContext, state: RecordState
    ) -> RecordingCommand:
        """MATCHING フェーズの処理。

        Returns:
            RecordingCommand: 実行すべきコマンド（副作用は UseCase で実行）
        """
        md = ctx.metadata

        # スケジュール変更検出
        if await self.analyzer.detect_schedule_change(frame):
            self.logger.info("スケジュール変更を検出、情報をリセット")
            self.event_bus.publish_domain_event(ScheduleChanged())
            return RecordingCommand.reset_metadata(
                ctx, reason="スケジュール変更検出"
            )

        # バトル開始検出
        if await self.analyzer.detect_session_start(frame, md.game_mode):
            self.logger.info("バトル開始を検出")

            # ドメインイベント発行
            event = BattleStarted(
                game_mode=str(md.game_mode) if md.game_mode else "unknown",
                rate=str(md.rate) if md.rate else None,
            )
            self.event_bus.publish_domain_event(event)

            return RecordingCommand.start_recording(
                ctx, reason="バトル開始検出"
            )

        return RecordingCommand.none(ctx)
