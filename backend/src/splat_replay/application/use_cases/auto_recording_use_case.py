"""Auto recording use case - 自動録画シナリオのオーケストレーション。

Phase 4 Refactoring: Handler が返す Command を実行し、Context を単一所有する。

責務:
- 自動録画の初期化
- メインループの実行
- Command の解釈と副作用の実行
- Context の管理（単一所有）
- 電源OFF検出
- クリーンアップ
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Literal, Mapping

from splat_replay.application.interfaces import CapturePort, LoggerPort
from splat_replay.application.services.recording.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.application.services.recording.frame_processing_service import (
    FrameProcessingService,
)
from splat_replay.application.services.recording.publisher_worker import (
    PublisherWorker,
)
from splat_replay.application.services.recording.commands import (
    RecordingAction,
    RecordingCommand,
)
from splat_replay.application.services.recording.phase_handler_registry import (
    PhaseHandlerRegistry,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.recording_session_service import (
    RecordingSessionService,
)
from splat_replay.application.services.recording.metadata_merger import (
    MetadataMerger,
)
from splat_replay.domain.models import (
    Frame,
    RecordingMetadata,
)
from splat_replay.domain.services import RecordState

WELCOME_MESSAGE = "🎮🎮🎮 Let's play! 🎮🎮🎮"

AutoRecordingState = Literal["idle", "running", "stopped"]


class AutoRecordingUseCase:
    """自動録画シナリオを実行する UseCase。

    このクラスは、自動録画の全体的な流れを制御します。
    Handler からの Command を解釈して副作用を実行します。
    Context は UseCase が単一所有し、Service に伝播します。
    """

    def __init__(
        self,
        session_service: RecordingSessionService,
        frame_processor: FrameProcessingService,
        phase_handlers: PhaseHandlerRegistry,
        context: RecordingContext,
        capture: CapturePort,
        capture_producer: FrameCaptureProducer,
        publisher_worker: PublisherWorker,
        logger: LoggerPort,
    ):
        self._session = session_service
        self._frame_processor = frame_processor
        self._phase_handlers = phase_handlers
        self._context = context
        self._capture = capture
        self._capture_producer = capture_producer
        self._publisher = publisher_worker
        self.logger = logger
        self._stop_event = asyncio.Event()
        self.last_phase = None
        self._state_lock = asyncio.Lock()
        self._state: AutoRecordingState = "idle"
        self._task: asyncio.Task[bool] | None = None
        self._context_lock = asyncio.Lock()
        self._context_revision = 0
        self._merger = MetadataMerger()

    # ================================================================
    # UseCase 実行
    # ================================================================
    async def execute(self) -> bool:
        """自動録画のメインシナリオを実行する。

        Returns:
            電源OFF検出フラグ（True: 電源OFFで終了、False: 通常終了）
        """
        if not await self._try_start():
            raise RuntimeError("自動録画は既に実行中です。")
        try:
            return await self._run()
        finally:
            await self._mark_stopped()

    async def start_background(self) -> bool:
        """自動録画をバックグラウンドで開始する。

        Returns:
            開始に成功した場合 True、既に実行中の場合 False
        """
        if not await self._try_start():
            return False

        async def _runner() -> bool:
            try:
                return await self._run()
            finally:
                await self._mark_stopped()

        self._task = asyncio.create_task(_runner())
        return True

    def status(self) -> AutoRecordingState:
        """現在の自動録画状態を返す。"""
        return self._state

    async def _run(self) -> bool:
        """自動録画のメインシナリオを実行する。

        Returns:
            電源OFF検出フラグ（True: 電源OFFで終了、False: 通常終了）
        """
        self.last_phase = None
        self.logger.info("自動録画開始")
        detected_power_off = False

        try:
            # Setup
            await self._setup()

            # Welcome message
            self.logger.info(WELCOME_MESSAGE)

            # Main loop
            detected_power_off = await self._run_main_loop()

        except Exception as e:
            self.logger.error("自動録画中にエラーが発生しました", error=str(e))

        finally:
            # Cleanup
            await self._teardown(detected_power_off)

        self.logger.info("自動録画終了")
        return detected_power_off

    async def _try_start(self) -> bool:
        async with self._state_lock:
            if self._state == "running":
                return False
            self._state = "running"
            return True

    async def _mark_stopped(self) -> None:
        async with self._state_lock:
            self._state = "stopped"

    # ================================================================
    # Setup / Teardown
    # ================================================================
    async def _setup(self) -> None:
        """自動録画の初期化。"""
        if self._stop_event.is_set():
            self._stop_event.clear()

        await self._session.setup()
        self._capture.setup()

        # Start background workers
        self._publisher.start()
        self._capture_producer.start()

    async def _teardown(self, detected_power_off: bool) -> None:
        """自動録画のクリーンアップ。

        Args:
            detected_power_off: 電源OFF検出フラグ
        """
        # 録画中なら停止
        if self._session.state in (RecordState.RECORDING, RecordState.PAUSED):
            await self._session.cancel()

        # Stop background workers
        self._capture_producer.stop()
        self._publisher.stop()

        # Cleanup
        self._capture.teardown()
        await self._session.teardown()

        # 電源OFF通知（最終）
        if detected_power_off:
            self._frame_processor.publish_power_off_detected(final=True)

    # ================================================================
    # Main Loop
    # ================================================================
    async def _run_main_loop(self) -> bool:
        """メインループを実行する。

        Returns:
            電源OFF検出フラグ
        """
        off_count = 0
        last_check = 0.0
        detected_power_off = False

        while not self._stop_event.is_set():
            # フレーム取得
            frame = await self._frame_processor.acquire_frame()
            if frame is None:
                # フレーム未到来。CPU スピン緩和のため譲歩。
                await asyncio.sleep(0.1)
                continue

            # 電源OFF検出
            (
                off_count,
                last_check,
                detected_power_off,
            ) = await self._frame_processor.check_power_off(
                frame, off_count, last_check
            )
            if detected_power_off:
                self.logger.info("電源OFFを検出、録画を停止")
                self._frame_processor.publish_power_off_detected()
                break

            # フェーズ変更ログ
            (
                context_snapshot,
                revision_snapshot,
            ) = await self._snapshot_context()
            phase = context_snapshot.phase(self._session.state)
            if self.last_phase != phase:
                self.logger.info(
                    f"フェーズが変更されました: {self.last_phase} -> {phase}"
                )
                self.last_phase = phase

            # フェーズ別処理（Command を取得）
            command = await self._phase_handlers.handle_frame(
                frame, context_snapshot, self._session.state
            )

            # Context を更新（UseCase が単一所有）
            await self._apply_command_context(
                base_context=context_snapshot,
                updated_context=command.updated_context,
                base_revision=revision_snapshot,
            )

            # Command を実行（副作用）
            await self._execute_command(command, base_context=context_snapshot)

        return detected_power_off

    # ================================================================
    # Command 実行
    # ================================================================
    async def _execute_command(
        self, command: RecordingCommand, *, base_context: RecordingContext
    ) -> None:
        """Handler からの Command を解釈して副作用を実行する。

        Args:
            command: 実行すべきコマンド
        """
        if command.action == RecordingAction.NONE:
            return

        if command.reason:
            self.logger.debug(
                f"Command 実行: {command.action.name} - {command.reason}"
            )

        # RecordingSessionService に context を渡す
        self._session.update_context(self._context)

        # Action に応じた副作用を実行
        action_handlers = {
            RecordingAction.START_RECORDING: self._session.start,
            RecordingAction.PAUSE_RECORDING: self._session.pause,
            RecordingAction.RESUME_RECORDING: self._session.resume,
            RecordingAction.STOP_RECORDING: self._handle_stop_recording,
            RecordingAction.CANCEL_RECORDING: self._session.cancel,
            RecordingAction.RESET_METADATA: self._session.reset_metadata,
        }

        handler = action_handlers.get(command.action)
        if handler:
            await handler()
            # Service の副作用実行後、最新の context を取得
            await self._sync_context_from_service(base_context=base_context)

    async def _handle_stop_recording(self) -> None:
        """録画停止処理（result_frame を渡す必要がある）。"""

        async def get_result_frame() -> Frame | None:
            return self._context.result_frame

        await self._session.stop(get_result_frame)

    async def _snapshot_context(self) -> tuple[RecordingContext, int]:
        async with self._context_lock:
            return self._context, self._context_revision

    async def _apply_command_context(
        self,
        *,
        base_context: RecordingContext,
        updated_context: RecordingContext,
        base_revision: int,
    ) -> None:
        async with self._context_lock:
            current_context = self._context
            if self._context_revision != base_revision:
                # MetadataMerger を使用して 3way マージ
                merged_metadata = self._merger.merge_with_auto_update(
                    base_context.metadata,
                    updated_context.metadata,
                    current_context.metadata,
                    current_context.manual_fields,
                )
                updated_context = replace(
                    updated_context, metadata=merged_metadata
                )
            # 手動編集フィールドで上書き
            manual_fields = current_context.manual_fields
            updated_metadata = self._merger.apply_manual_overrides(
                current_context.metadata,
                updated_context.metadata,
                manual_fields,
            )
            updated_context = replace(
                updated_context,
                metadata=updated_metadata,
                manual_fields=manual_fields,
                pending_result_updates=(
                    {}
                    if self._is_reset_context(updated_context)
                    else current_context.pending_result_updates
                ),
            )
            self._context = updated_context
            self._context_revision += 1

    async def _sync_context_from_service(
        self, *, base_context: RecordingContext
    ) -> None:
        """Service から最新の Context を同期する。

        Note:
            Service の副作用（start/stop等）が context を更新する場合があるため、
            実行後に同期が必要。将来的には Service が context を
            返すようにすればこの同期処理は不要。
        """
        updated_context = self._session.context
        async with self._context_lock:
            current_context = self._context
            # MetadataMerger を使用して 3way マージ
            merged_metadata = self._merger.merge_with_auto_update(
                base_context.metadata,
                updated_context.metadata,
                current_context.metadata,
                current_context.manual_fields,
            )
            manual_fields = updated_context.manual_fields
            # 手動編集フィールドで上書き
            merged_metadata = self._merger.apply_manual_overrides(
                current_context.metadata,
                merged_metadata,
                manual_fields,
            )
            if self._is_reset_context(updated_context):
                pending_result_updates = {}
            else:
                pending_result_updates = (
                    current_context.pending_result_updates
                    if current_context.pending_result_updates
                    != base_context.pending_result_updates
                    else updated_context.pending_result_updates
                )
            self._context = replace(
                updated_context,
                metadata=merged_metadata,
                manual_fields=manual_fields,
                pending_result_updates=pending_result_updates,
            )
            self._context_revision += 1

    async def get_metadata(self) -> RecordingMetadata:
        """現在の録画メタデータを取得する。"""
        async with self._context_lock:
            return self._context.metadata

    async def update_metadata(
        self, updates: Mapping[str, object]
    ) -> RecordingMetadata:
        """録画メタデータを更新する。"""
        if not updates:
            async with self._context_lock:
                return self._context.metadata

        async with self._context_lock:
            current_context = self._context
            combined_updates = dict(updates)
            if (
                current_context.metadata.result is None
                and current_context.pending_result_updates
            ):
                combined_updates = {
                    **current_context.pending_result_updates,
                    **combined_updates,
                }
            # MetadataMerger を使用して更新を適用
            updated_metadata, applied_fields = (
                self._merger.apply_manual_updates(
                    current_context.metadata, combined_updates
                )
            )
            manual_fields = current_context.manual_fields.union(applied_fields)
            if updated_metadata.result is None:
                result_fields = (
                    RecordingMetadata.BATTLE_FIELDS
                    | RecordingMetadata.SALMON_FIELDS
                )
                pending_result_updates = {
                    key: value
                    for key, value in combined_updates.items()
                    if key in result_fields
                }
            else:
                pending_result_updates = {}
            if (
                updated_metadata == current_context.metadata
                and manual_fields == current_context.manual_fields
                and pending_result_updates
                == current_context.pending_result_updates
            ):
                return updated_metadata
            new_context = replace(
                current_context,
                metadata=updated_metadata,
                manual_fields=manual_fields,
                pending_result_updates=pending_result_updates,
            )
            self._context = new_context
            self._context_revision += 1
        self._session.update_context(new_context)
        if updated_metadata != current_context.metadata:
            self._session.publish_metadata_updated(updated_metadata)
        return updated_metadata

    # ================================================================
    # ヘルパー
    # ================================================================
    def force_stop(self) -> None:
        """メインループを強制停止する。"""
        self._stop_event.set()

    @staticmethod
    def _is_reset_context(context: RecordingContext) -> bool:
        return (
            context.metadata.started_at is None
            and context.battle_started_at == 0.0
            and context.result_frame is None
            and not context.finish
            and not context.completed
            and not context.manual_fields
            and not context.pending_result_updates
        )
