"""Recording session service - 録画セッションの制御。

Phase 4 Refactoring: Context は UseCase が単一所有し、Service は状態管理のみを担当。
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import TYPE_CHECKING, Literal

from splat_replay.application.interfaces import (
    DomainEventPublisher,
    LoggerPort,
    RecorderWithTranscriptionPort,
    VideoAssetRepositoryPort,
)
from splat_replay.application.services.recording.metadata_merger import (
    MetadataMerger,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.domain.events import (
    RecordingCancelled,
    RecordingMetadataUpdated,
    RecordingPaused,
    RecordingResumed,
    RecordingStarted,
    RecordingStopped,
)
from splat_replay.domain.models import Frame, RecordingMetadata
from splat_replay.domain.models.result import BattleResult
from splat_replay.domain.services import (
    FrameAnalyzer,
    RecordEvent,
    RecordState,
    StateMachine,
)

if TYPE_CHECKING:
    from typing import Awaitable, Callable


class RecordingSessionService:
    """録画セッションの制御を担当するサービス。

    責務:
    - 状態遷移（StateMachine との同期）
    - Recorder 制御（start/pause/resume/stop/cancel）
    - メタデータ管理
    - ビデオアセット保存
    - 結果詳細の抽出（停止後）

    注意:
    - Context は UseCase が単一所有し、このサービスは参照のみ（状態管理のため）
    - 副作用（録画開始/停止等）はこのサービスで実行され、結果として context が更新される
    """

    def __init__(
        self,
        state_machine: StateMachine,
        recorder: RecorderWithTranscriptionPort,
        asset_repository: VideoAssetRepositoryPort,
        analyzer: FrameAnalyzer,
        logger: LoggerPort,
        context: RecordingContext,
        domain_publisher: DomainEventPublisher | None = None,
    ):
        self.sm = state_machine
        self.recorder = recorder
        self.asset_repository = asset_repository
        self.analyzer = analyzer
        self.logger = logger
        self._ctx = context
        self._domain_publisher = domain_publisher
        self._pending_stop_reason: Literal["stop", "cancel"] | None = None

        # StateMachine のリスナーを登録
        self.sm.add_listener(self._on_state_change)

        # Recorder のリスナーを登録
        self.recorder.add_status_listener(self._on_recorder_status_change)

    # ================================================================    # Properties
    # ================================================================
    @property
    def context(self) -> RecordingContext:
        """現在の録画コンテキストを取得する（UseCase から参照される）。"""
        return self._ctx

    @property
    def state(self) -> RecordState:
        """現在の録画状態を取得する。"""
        return self.sm.state

    def update_context(self, context: RecordingContext) -> None:
        """コンテキストを更新する（UseCase から呼ばれる）。

        Note:
            UseCase が Context を単一所有し、Service には参照を渡す。
            Service 側の副作用（start/stop等）で context が更新された場合、
            UseCase は Service から最新の context を取得する必要がある。
        """
        self._ctx = context

    # ================================================================    # Setup / Teardown
    # ================================================================
    async def setup(self) -> None:
        """録画環境のセットアップ。"""
        await self.recorder.setup()

    async def teardown(self) -> None:
        """録画環境のクリーンアップ。"""
        await self.recorder.teardown()

    # ================================================================
    # 状態遷移
    # ================================================================
    async def _on_state_change(self, state: RecordState) -> None:
        """StateMachine の状態変更を通知する。"""
        self.logger.info("録画状態が変化しました", state=state.name)

    async def _on_recorder_status_change(
        self, status_message: str, *_: object
    ) -> None:
        """Recorder の状態変更を通知する。

        Args:
            status_message: 録画状態（"started", "paused", "resumed", "stopped"）
        """
        self.logger.debug("録画機器の状態", message=status_message)

        # OBS手動開始を検出
        if (
            status_message == "started"
            and self.sm.state == RecordState.STOPPED
        ):
            self.logger.info(
                "外部操作で録画が開始されました。バトル状態に遷移します。"
            )
            # マッチング開始時間が設定されていなければ現在時刻を設定
            if self._ctx.battle_started_at is None:
                self._ctx = replace(self._ctx, battle_started_at=time.time())
            # StateMachine を RECORDING に遷移
            try:
                await self.sm.handle(RecordEvent.START)
            except Exception as e:
                self.logger.warning("状態遷移に失敗しました", error=str(e))
        # OBS手動一時停止を検出
        if (
            status_message == "paused"
            and self.sm.state == RecordState.RECORDING
        ):
            self.logger.info("外部操作で録画が一時停止されました。")
            # StateMachine を PAUSED に遷移
            try:
                await self.sm.handle(RecordEvent.PAUSE)
            except Exception as e:
                self.logger.warning("状態遷移に失敗しました", error=str(e))

        # OBS手動再開を検出
        if status_message == "resumed" and self.sm.state == RecordState.PAUSED:
            self.logger.info("外部操作で録画が再開されました。")
            # StateMachine を RECORDING に遷移
            try:
                await self.sm.handle(RecordEvent.RESUME)
            except Exception as e:
                self.logger.warning("状態遷移に失敗しました", error=str(e))

        # OBS手動停止を検出してリセット
        if (
            status_message == "stopped"
            and self.sm.state != RecordState.STOPPED
        ):
            self.logger.warning(
                "外部操作で録画が停止されました。状態をリセットします。"
            )
            # StateMachine を STOPPED に遷移
            try:
                await self.sm.handle(RecordEvent.STOP)
            except Exception as e:
                self.logger.warning(
                    "状態遷移に失敗しました（既に停止済みの可能性）",
                    error=str(e),
                )
            # Context をリセット
            await self.reset()

        # 録画状態イベントはOBSの状態通知で統一して発行する
        self._publish_recorder_state_event(status_message)

    # ================================================================
    # 録画制御
    # ================================================================
    async def start(self) -> None:
        """録画を開始する。"""
        if self.sm.state is not RecordState.STOPPED:
            self.logger.warning("Recording already started")
            return
        self._ctx = replace(self._ctx, battle_started_at=time.time())
        await self.sm.handle(RecordEvent.START)
        await self.recorder.start()

    async def pause(self) -> None:
        """録画を一時停止する。"""
        if self.sm.state is not RecordState.RECORDING:
            self.logger.warning("Recording not in progress")
            return
        await self.sm.handle(RecordEvent.PAUSE)
        await self.recorder.pause()

    async def resume(self) -> None:
        """録画を再開する。"""
        if self.sm.state is not RecordState.PAUSED:
            self.logger.warning("Recording not paused")
            return
        await self.sm.handle(RecordEvent.RESUME)
        await self.recorder.resume()

    async def cancel(self) -> None:
        """録画を中止する（ファイル削除）。"""
        self._pending_stop_reason = "cancel"
        await self.sm.handle(RecordEvent.STOP)
        await self.recorder.cancel()
        await self.reset()

    async def stop(
        self, get_result_frame: Callable[[], Awaitable[Frame | None]]
    ) -> None:
        """録画を停止し、ビデオアセットを保存する。

        Args:
            get_result_frame: 結果フレーム取得関数（結果画面がない場合に使用）
        """
        if self.sm.state is RecordState.STOPPED:
            self.logger.warning("No recording found")
            return

        self._pending_stop_reason = "stop"
        await self.sm.handle(RecordEvent.STOP)
        video, srt = await self.recorder.stop()
        self.logger.info("録画を停止", video=str(video))
        if video is None:
            self.logger.error("Recording failed")
            return

        # 結果フレームの取得
        if self._ctx.result_frame is None:
            frame = await get_result_frame()
            if frame is not None:
                self._ctx = replace(self._ctx, result_frame=frame)

        # 結果フレームから詳細情報を抽出（停止後の非ブロッキング処理）
        if (
            self._ctx.result_frame is not None
            and self._ctx.metadata.result is None
        ):
            base_metadata = self._ctx.metadata
            manual_fields = self._ctx.manual_fields
            pending_result_updates = self._ctx.pending_result_updates
            result = await self.analyzer.extract_session_result(
                self._ctx.result_frame, self._ctx.metadata.game_mode
            )
            if result is not None and isinstance(result, BattleResult):
                merger = MetadataMerger()
                updated_metadata = replace(base_metadata, result=result)
                if manual_fields:
                    updated_metadata = merger.apply_manual_overrides(
                        current=base_metadata,
                        updated=updated_metadata,
                        manual_fields=manual_fields,
                    )
                if pending_result_updates:
                    updated_metadata, applied_fields = (
                        merger.apply_pending_result_updates(
                            updated_metadata,
                            pending_result_updates,
                            manual_fields,
                        )
                    )
                    if applied_fields:
                        manual_fields = manual_fields.union(applied_fields)
                    pending_result_updates = {}
                self._ctx = replace(
                    self._ctx,
                    metadata=updated_metadata,
                    manual_fields=manual_fields,
                    pending_result_updates=pending_result_updates,
                )
                self.logger.info(
                    "結果詳細を取得",
                    match=str(result.match),
                    rule=str(result.rule),
                    stage=str(result.stage),
                    kill=result.kill,
                    death=result.death,
                    special=result.special,
                )
                # メタデータ更新通知
                if self._domain_publisher:
                    self._domain_publisher.publish_domain_event(
                        RecordingMetadataUpdated(
                            metadata=self._ctx.metadata.to_dict()
                        )
                    )

        asset = self.asset_repository.save_recording(
            video=video,
            srt=srt,
            screenshot=self._ctx.result_frame,
            metadata=self._ctx.metadata,
        )
        self.logger.info("ビデオアセットを保存", asset=str(asset))

        # 録画停止後、次のバトル検出のためにコンテキストをリセット
        await self.reset()

    async def reset(self) -> None:
        """メタデータをリセットする。"""
        from splat_replay.domain.models import RecordingMetadata

        self._ctx = RecordingContext(
            metadata=RecordingMetadata(game_mode=self._ctx.metadata.game_mode)
        )
        self.logger.info("メタデータをリセット")
        # Note: リセット時は RecordingMetadataUpdated を発行しない
        # フロントエンドは録画状態のSTOPPEDでメタデータをリセットする

    async def reset_metadata(self) -> None:
        """メタデータをリセットする（reset のエイリアス）。"""
        await self.reset()

    def _publish_recorder_state_event(self, status_message: str) -> None:
        """OBSの録画状態イベントをドメインイベントとして発行する。"""
        if self._domain_publisher is None:
            return

        if status_message == "started":
            event = RecordingStarted(
                session_id="current",
                game_mode=(
                    self._ctx.metadata.game_mode.name
                    if self._ctx.metadata.game_mode
                    else None
                ),
                rate=(
                    str(self._ctx.metadata.rate)
                    if self._ctx.metadata.rate
                    else None
                ),
            )
        elif status_message == "paused":
            event = RecordingPaused(session_id="current")
        elif status_message == "resumed":
            event = RecordingResumed(session_id="current")
        elif status_message == "stopped":
            if self._pending_stop_reason == "cancel":
                event = RecordingCancelled(session_id="current")
            else:
                duration = (
                    time.time() - self._ctx.battle_started_at
                    if self._ctx.battle_started_at
                    else None
                )
                event = RecordingStopped(
                    session_id="current",
                    duration_seconds=duration,
                )
            self._pending_stop_reason = None
        else:
            return

        self._domain_publisher.publish_domain_event(event)

    def publish_metadata_updated(self, metadata: RecordingMetadata) -> None:
        """メタデータ更新イベントを発行する。"""
        if self._domain_publisher is None:
            return
        self._domain_publisher.publish_domain_event(
            RecordingMetadataUpdated(metadata=metadata.to_dict())
        )

    # ================================================================
    # クエリ
    # ================================================================
    @property
    def metadata(self) -> RecordingMetadata:
        """現在のメタデータを返す。"""
        return self._ctx.metadata
