"""Standby phase handler - マッチング前の待機状態。

Phase 4 Refactoring: Handler を純粋関数化し、副作用ではなく Command を返す。
"""

from __future__ import annotations

from dataclasses import replace

from splat_replay.application.interfaces import EventBusPort, LoggerPort
from splat_replay.application.services.recording.commands import (
    RecordingCommand,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.domain.events import (
    BattleMatchingStarted,
    RecordingMetadataUpdated,
)
from splat_replay.domain.models import Frame
from splat_replay.domain.services import FrameAnalyzer, RecordState


class StandbyPhaseHandler:
    """STANDBY フェーズ（マッチング前）の処理。

    責務:
    - ゲームモード検出
    - レート検出
    - マッチング開始検出
    - 検出結果に応じた Command を返す（このフェーズは副作用なし）
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
        """STANDBY フェーズの処理。

        Returns:
            RecordingCommand: 実行すべきコマンド（このフェーズでは副作用なし）
        """
        md = ctx.metadata

        # ゲームモード・レート検出
        if await self.analyzer.detect_match_select(frame):
            updated = False
            updates = {}

            detected_mode = await self.analyzer.extract_game_mode(frame)
            if detected_mode is not None and detected_mode != md.game_mode:
                updates["game_mode"] = detected_mode
                updated = True
                self.logger.info("ゲームモード取得", mode=str(detected_mode))

            detected_rate = await self.analyzer.extract_rate(
                frame, md.game_mode
            )
            if detected_rate is not None and (
                not isinstance(detected_rate, type(md.rate))
                or detected_rate != md.rate
            ):
                updates["rate"] = detected_rate
                updated = True
                self.logger.info("レート取得", rate=str(detected_rate))

            if updated:
                ctx = replace(ctx, metadata=replace(ctx.metadata, **updates))
                self.event_bus.publish_domain_event(
                    RecordingMetadataUpdated(metadata=ctx.metadata.to_dict())
                )

        # マッチング開始検出
        if await self.analyzer.detect_matching_start(frame):
            import datetime

            self.logger.info("マッチング開始を検出")

            ctx = replace(
                ctx,
                metadata=replace(
                    ctx.metadata, started_at=datetime.datetime.now()
                ),
            )

            # ドメインイベント発行
            event = BattleMatchingStarted(
                game_mode=str(ctx.metadata.game_mode)
                if ctx.metadata.game_mode
                else "unknown",
                rate=str(ctx.metadata.rate) if ctx.metadata.rate else None,
            )
            self.event_bus.publish_domain_event(event)

            # メタデータ更新通知（既存イベント）
            self.event_bus.publish_domain_event(
                RecordingMetadataUpdated(metadata=ctx.metadata.to_dict())
            )

        return RecordingCommand.none(ctx)
