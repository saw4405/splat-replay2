"""Paused state handler - 一時停止中の処理。

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
from splat_replay.domain.models import Frame
from splat_replay.domain.services import RecordState


class PausedStateHandler:
    """PAUSED 状態（一時停止中）の処理。

    責務:
    - resume_trigger の評価
    - 録画再開判定
    - 検出結果に応じた Command を返す（副作用は UseCase で実行）
    """

    def __init__(
        self,
        logger: LoggerPort,
        event_bus: EventBusPort,
    ):
        self.logger = logger
        self.event_bus = event_bus

    async def handle(
        self, frame: Frame, ctx: RecordingContext, state: RecordState
    ) -> RecordingCommand:
        """PAUSED 状態の処理。

        Returns:
            RecordingCommand: 実行すべきコマンド（副作用は UseCase で実行）
        """
        if ctx.resume_trigger and await ctx.resume_trigger(frame):
            self.logger.info("録画を再開")
            # Note: RecordingResumed イベントは RecordingCommand.resume_recording 実行時に発行される
            return RecordingCommand.resume_recording(
                ctx, reason="resume_trigger 条件成立"
            )

        return RecordingCommand.none(ctx)
