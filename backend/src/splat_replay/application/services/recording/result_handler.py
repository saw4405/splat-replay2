"""Result phase handler - 結果画面の処理。

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
from splat_replay.domain.services import FrameAnalyzer, RecordState


class ResultPhaseHandler:
    """RESULT フェーズ（結果画面）の処理。

    責務:
    - 結果画面の継続判定
    - 結果画面からの遷移検出

    Note:
        結果詳細（マッチ・ルール・ステージ・キルレ）の抽出は時間がかかるため、
        録画停止を優先し、詳細情報は result_frame から後で抽出される。
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
        """結果画面表示中の処理。

        Args:
            frame: 処理対象のフレーム
            ctx: 録画コンテキスト
            state: 現在の録画状態

        Returns:
            RecordingCommand: 実行すべきコマンド（副作用は UseCase で実行）

        Note:
            結果詳細（マッチ・ルール・ステージ・キルレ）の抽出は時間がかかるため、
            結果画面での処理はスキップし、遷移検出のみを行う。
            詳細情報は録画停止後に result_frame から抽出される。
        """
        # 既に停止済みの場合は何もしない
        if state is RecordState.STOPPED:
            return RecordingCommand.none(ctx)

        gm = ctx.metadata.game_mode

        # 結果画面の継続判定（遷移したら即座に停止）
        still_result = await self.analyzer.detect_session_result(frame, gm)
        if not still_result:
            self.logger.info("結果画面から遷移")
            # Note: RecordingStopped イベントは RecordingCommand.stop_recording 実行時に発行される
            return RecordingCommand.stop_recording(
                ctx, reason="結果画面から遷移"
            )

        return RecordingCommand.none(ctx)
