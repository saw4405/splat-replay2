"""PostFinish phase handler - バトル終了後の判定検出。

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
    BattleResultDetected,
    RecordingMetadataUpdated,
    RecordingPaused,
)
from splat_replay.domain.models import Frame
from splat_replay.domain.services import FrameAnalyzer, RecordState


class PostFinishPhaseHandler:
    """POST_FINISH フェーズ（バトル終了後）の処理。

    責務:
    - バトルジャッジメント検出
    - ローディング画面検出
    - 結果画面検出
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
        """POST_FINISH フェーズの処理。"""
        gm = ctx.metadata.game_mode

        # バトルジャッジメント検出
        if (
            ctx.metadata.judgement is None
            and await self.analyzer.detect_session_judgement(frame, gm)
        ):
            self.logger.info("バトル判定を検出")
            judgement = await self.analyzer.extract_session_judgement(
                frame, gm
            )
            if judgement is not None and ctx.metadata.judgement is None:
                ctx = replace(
                    ctx, metadata=replace(ctx.metadata, judgement=judgement)
                )
                self.logger.info(
                    "バトルジャッジメント取得", judgement=str(judgement)
                )
                # ドメインイベント発行
                result_str = str(judgement).lower()
                self.event_bus.publish_domain_event(
                    BattleResultDetected(result=result_str)
                )
                # メタデータ更新通知（既存イベント）
                self.event_bus.publish_domain_event(
                    RecordingMetadataUpdated(metadata=ctx.metadata.to_dict())
                )
            return RecordingCommand.none(ctx)

        # ローディング画面検出
        if await self.analyzer.detect_loading(frame):
            self.logger.info("ローディング画面を検出、一時停止")
            self.event_bus.publish_domain_event(
                RecordingPaused(
                    session_id="current", reason="loading_detected"
                )
            )
            updated_ctx = replace(
                ctx, resume_trigger=self.analyzer.detect_loading_end
            )
            return RecordingCommand.pause_recording(
                updated_ctx, reason="ローディング画面検出"
            )

        # 結果画面検出
        if await self.analyzer.detect_session_result(frame, gm):
            self.logger.info("結果画面を検出")
            return RecordingCommand.none(replace(ctx, result_frame=frame))

        return RecordingCommand.none(ctx)
