"""In-game phase handler - バトル中の処理。

Phase 4 Refactoring: Handler を純粋関数化し、副作用ではなく Command を返す。
"""

from __future__ import annotations

import time
from dataclasses import replace

from splat_replay.application.interfaces import EventBusPort, LoggerPort
from splat_replay.application.services.recording.commands import (
    RecordingCommand,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.weapon_detection_service import (
    WeaponDetectionService,
)
from splat_replay.domain.events import BattleFinished, BattleInterrupted
from splat_replay.domain.models import Frame
from splat_replay.domain.services import FrameAnalyzer, RecordState

# 定数
BATTLE_ABORT_BASE_SECONDS = 60  # バトル中断判定の基準時間
ABORT_DISPLAY_DELAY_SECONDS = 30  # 中断表示までのタイムラグ
EARLY_ABORT_WINDOW_SECONDS = (
    BATTLE_ABORT_BASE_SECONDS + ABORT_DISPLAY_DELAY_SECONDS
)  # 実際の検出時間（90秒）
MAX_RECORDING_SECONDS = 600


class InGamePhaseHandler:
    """IN_GAME フェーズ（バトル中）の処理。

    責務:
    - バトル中断検出
    - 録画時間制限
    - バトル終了検出
    - 通信エラー検出
    - 検出結果に応じた Command を返す（副作用は UseCase で実行）
    """

    def __init__(
        self,
        analyzer: FrameAnalyzer,
        logger: LoggerPort,
        event_bus: EventBusPort,
        weapon_detection_service: WeaponDetectionService | None = None,
    ):
        self.analyzer = analyzer
        self.logger = logger
        self.event_bus = event_bus
        self.weapon_detection_service = weapon_detection_service

    async def handle(
        self, frame: Frame, ctx: RecordingContext, state: RecordState
    ) -> RecordingCommand:
        """IN_GAME フェーズの処理。

        Returns:
            RecordingCommand: 実行すべきコマンド（副作用は UseCase で実行）
        """
        gm = ctx.metadata.game_mode
        now = time.time()

        # バトル中断検出（開始60秒以内）
        if (
            now - ctx.battle_started_at <= EARLY_ABORT_WINDOW_SECONDS
            and await self.analyzer.detect_session_abort(frame, gm)
        ):
            self.logger.info("バトル中断を検出したため録画を中止")
            self.event_bus.publish_domain_event(
                BattleInterrupted(reason="early_abort")
            )
            return RecordingCommand.cancel_recording(
                ctx, reason="バトル中断検出"
            )

        # 録画時間制限（10分）
        if now - ctx.battle_started_at >= MAX_RECORDING_SECONDS:
            self.logger.info("録画が10分以上続いたため停止")
            # Note: 時間制限超過は異常系ではないため、専用のドメインイベントは不要
            # UI通知が必要な場合は RecordingTimeLimitExceeded イベントを追加すべき
            return RecordingCommand.stop_recording(
                ctx, reason="録画時間制限（10分）"
            )

        # ブキ判別（20秒以内・表示画面時のみ）
        if self.weapon_detection_service is not None:
            ctx = await self.weapon_detection_service.process(
                frame=frame,
                context=ctx,
            )

        # バトル終了検出
        if await self.analyzer.detect_session_finish(frame, gm):
            duration = now - ctx.battle_started_at
            self.logger.info("バトル終了を検出、一時停止")
            self.event_bus.publish_domain_event(
                BattleFinished(duration_seconds=duration)
            )
            # コンテキストを更新（不変性保持）
            updated_ctx = replace(
                ctx,
                finish=True,
                resume_trigger=lambda f: self.analyzer.detect_session_judgement(
                    f, gm
                ),
            )
            return RecordingCommand.pause_recording(
                updated_ctx, reason="バトル終了検出"
            )

        # 通信エラー検出
        if await self.analyzer.detect_communication_error(frame, gm):
            self.logger.info("通信エラーを検出")
            self.event_bus.publish_domain_event(
                BattleInterrupted(reason="communication_error")
            )
            return RecordingCommand.cancel_recording(
                ctx, reason="通信エラー検出"
            )

        return RecordingCommand.none(ctx)
