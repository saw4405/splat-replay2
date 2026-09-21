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
from collections.abc import Callable
from datetime import datetime
from dataclasses import replace
from typing import Literal, Mapping

from splat_replay.application.interfaces import (
    CaptureDevicePort,
    CapturePort,
    LoggerPort,
    ReplayBootstrapResolverPort,
)
from splat_replay.application.metadata import (
    BATTLE_METADATA_FIELDS,
    SALMON_METADATA_FIELDS,
)
from splat_replay.application.services.recording.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.application.services.recording.frame_processing_service import (
    FrameProcessingService,
    POWER_OFF_CHECK_INTERVAL,
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
    GameMode,
    RecordingMetadata,
    SwitchPowerMonitor,
    SwitchPowerState,
)
from splat_replay.domain.services import RecordState

WELCOME_MESSAGE = "🎮🎮🎮 Let's play! 🎮🎮🎮"

AutoRecordingState = Literal["idle", "running", "stopped"]
BACKGROUND_RETRY_DELAY_SECONDS = 5.0
CAPTURE_DEVICE_CHECK_INTERVAL_SECONDS = 1.0
POWER_ON_WAIT_CAPTURE_INTERVAL_SECONDS = 1.0
CAPTURE_DISCONNECTED_RETRY_INTERVAL_SECONDS = 1.0
POWER_ON_CHECK_INTERVAL_SECONDS = 0.0
UNTHROTTLED_CAPTURE_INTERVAL_SECONDS = 0.0
CAPTURE_INTERVAL_BY_POWER_STATE: Mapping[SwitchPowerState, float | None] = {
    SwitchPowerState.UNKNOWN: POWER_ON_WAIT_CAPTURE_INTERVAL_SECONDS,
    SwitchPowerState.ARMED: UNTHROTTLED_CAPTURE_INTERVAL_SECONDS,
    SwitchPowerState.WAITING_FOR_POWER_ON: (
        POWER_ON_WAIT_CAPTURE_INTERVAL_SECONDS
    ),
    SwitchPowerState.CAPTURE_DISCONNECTED: (
        CAPTURE_DISCONNECTED_RETRY_INTERVAL_SECONDS
    ),
    SwitchPowerState.STOPPED: None,
}


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
        replay_bootstrap_resolver: ReplayBootstrapResolverPort | None = None,
        background_retry_delay_seconds: float = BACKGROUND_RETRY_DELAY_SECONDS,
        capture_device: CaptureDevicePort | None = None,
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
        self._last_record_state: RecordState | None = None
        self._merger = MetadataMerger()
        self._replay_bootstrap_resolver = replay_bootstrap_resolver
        self._power_monitor = SwitchPowerMonitor()
        self._background_retry_delay_seconds = background_retry_delay_seconds
        self._capture_device = capture_device
        self._audio_preparation_task: asyncio.Task[None] | None = None
        self.power_off_count = 0
        self.maintenance_check: Callable[[], bool] | None = None

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
            return await self._run(continuous=False)
        finally:
            await self._mark_stopped()

    async def start_background(self) -> bool:
        """自動録画をバックグラウンドで開始する。

        Returns:
            開始に成功した場合 True、既に実行中の場合 False
        """
        if not await self._try_start():
            return False
        if self._stop_event.is_set():
            self._stop_event.clear()

        async def _runner() -> bool:
            saw_power_off = False
            try:
                while not self._stop_event.is_set():
                    # セットアップ失敗後も、後片付け済みの境界で終了要求を評価する。
                    if (
                        self.maintenance_check is not None
                        and self.maintenance_check()
                    ):
                        await asyncio.sleep(0.1)
                        continue
                    try:
                        saw_power_off = (
                            await self._run(continuous=True) or saw_power_off
                        )
                    except Exception as exc:  # noqa: BLE001
                        self.logger.error(
                            "常駐自動録画の実行に失敗しました",
                            error=str(exc),
                        )
                    if self._stop_event.is_set():
                        break
                    self.logger.warning(
                        "常駐自動録画を再試行します",
                        delay_seconds=self._background_retry_delay_seconds,
                    )
                    await asyncio.sleep(self._background_retry_delay_seconds)
                return saw_power_off
            finally:
                await self._mark_stopped()

        self._task = asyncio.create_task(_runner())
        return True

    def status(self) -> AutoRecordingState:
        """現在の自動録画状態を返す。"""
        return self._state

    def power_status(self) -> SwitchPowerState:
        """現在のSwitch電源監視状態を返す。"""
        return self._power_monitor.state

    async def stop_background(self) -> None:
        """常駐自動録画を停止し、後片付けの完了まで待つ。"""
        self.force_stop()
        task = self._task
        if task is not None:
            await task

    async def _run(self, *, continuous: bool) -> bool:
        """自動録画のメインシナリオを実行する。

        Returns:
            電源OFF検出フラグ（True: 電源OFFで終了、False: 通常終了）
        """
        self.last_phase = None
        self._last_record_state = self._session.state
        self._power_monitor = SwitchPowerMonitor()
        self.logger.info("自動録画開始")
        detected_power_off = False

        try:
            # Setup
            await self._setup()

            # Welcome message
            self.logger.info(WELCOME_MESSAGE)

            # Main loop
            detected_power_off = await self._run_main_loop(
                continuous=continuous
            )

        except Exception as exc:
            self.logger.error(
                "自動録画中にエラーが発生しました",
                error=str(exc),
            )
            if continuous:
                raise
        finally:
            # Cleanup
            await self._teardown()

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
        await self._apply_replay_bootstrap()

        # Start background workers
        self._publisher.start()
        self._apply_capture_interval_for_power_state()
        self._capture_producer.start()

    async def _teardown(self) -> None:
        """自動録画のクリーンアップ。"""
        self._power_monitor = self._power_monitor.stop()
        await self._cancel_audio_preparation()
        self._phase_handlers.cancel_background_tasks()

        # 録画中なら停止
        if self._session.state in (RecordState.RECORDING, RecordState.PAUSED):
            await self._session.cancel()

        # Stop background workers
        self._capture_producer.stop()
        self._publisher.stop()

        # Cleanup
        self._capture.teardown()
        await self._session.teardown()

    # ================================================================
    # Main Loop
    # ================================================================
    async def _run_main_loop(self, *, continuous: bool = True) -> bool:
        """メインループを実行する。

        Returns:
            電源OFF検出フラグ
        """
        last_check = 0.0
        last_device_check = 0.0
        saw_power_off = False
        pending_power_on_frames: list[Frame] = []

        while not self._stop_event.is_set():
            # フレーム処理の境界でのみ保守へ移行し、録画開始と競合させない。
            if self.maintenance_check is not None and self.maintenance_check():
                await asyncio.sleep(0.1)
                continue
            # フレーム取得
            frame = await self._frame_processor.acquire_frame()
            synced = await self._sync_context_if_state_changed()
            if frame is None:
                now = asyncio.get_running_loop().time()
                if (
                    self._capture_device is not None
                    and now - last_device_check
                    >= CAPTURE_DEVICE_CHECK_INTERVAL_SECONDS
                ):
                    last_device_check = now
                    connected = await asyncio.to_thread(
                        self._capture_device.is_connected
                    )
                    if not connected:
                        pending_power_on_frames.clear()
                        await self._handle_capture_disconnect_transition()
                # フレーム未到来。CPU スピン緩和のため譲歩。
                await asyncio.sleep(0.1)
                continue
            if synced:
                continue

            # 電源OFF検出
            try:
                (
                    last_check,
                    power_is_off,
                ) = await self._frame_processor.observe_power_off(
                    frame,
                    last_check,
                    (
                        POWER_ON_CHECK_INTERVAL_SECONDS
                        if self._power_monitor.state
                        is not SwitchPowerState.ARMED
                        else POWER_OFF_CHECK_INTERVAL
                    ),
                )
                if power_is_off is not None:
                    previous_power_state = self._power_monitor.state
                    if (
                        power_is_off is False
                        and previous_power_state is not SwitchPowerState.ARMED
                    ):
                        pending_power_on_frames.append(frame)
                        pending_power_on_frames = pending_power_on_frames[
                            -self._power_monitor.on_threshold :
                        ]
                    elif power_is_off:
                        pending_power_on_frames.clear()
                    self._power_monitor, request_post_process = (
                        self._power_monitor.observe(power_is_off=power_is_off)
                    )
                    current_power_state = self._power_monitor.state
                    if previous_power_state is not current_power_state:
                        self._apply_capture_interval_for_power_state()
                        self.logger.info(
                            "Switch電源監視状態が変化しました",
                            previous=previous_power_state.value,
                            current=current_power_state.value,
                        )
                        self.last_phase = None
                        await self._refresh_audio_health_for_power_state()
                    if request_post_process:
                        saw_power_off = True
                        await self._handle_power_off_transition()
                        if not continuous:
                            break

                if self._power_monitor.state is not SwitchPowerState.ARMED:
                    continue

                frames_to_process = pending_power_on_frames or [frame]
                pending_power_on_frames = []
                for armed_frame in frames_to_process:
                    if self._stop_event.is_set():
                        break
                    await self._process_armed_frame_safely(armed_frame)

            except Exception as e:
                pending_power_on_frames.clear()
                self.logger.exception(
                    "メインループ内でのフレーム解析に失敗しました。フレームをスキップして処理を継続します。",
                    error=str(e),
                )
                # CPUの過剰スピンを防止するため少量のウェイトを挟む
                await asyncio.sleep(0.01)

        return saw_power_off

    async def _process_armed_frame_safely(self, frame: Frame) -> None:
        """ON確定後の一フレームを処理し、他の候補フレームへ影響させない。"""
        try:
            await self._process_armed_frame(frame)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception(
                "メインループ内でのフレーム解析に失敗しました。フレームをスキップして処理を継続します。",
                error=str(exc),
            )
            await asyncio.sleep(0.01)

    async def _process_armed_frame(self, frame: Frame) -> None:
        """電源ON確定済みのフレームを現在のフェーズへ一度だけ渡す。"""
        context_snapshot, revision_snapshot = await self._snapshot_context()
        phase = context_snapshot.phase(self._session.state)
        if self.last_phase != phase:
            self.logger.info(
                f"フェーズが変更されました: {self.last_phase} -> {phase}"
            )
            self.last_phase = phase

        command = await self._phase_handlers.handle_frame(
            frame, context_snapshot, self._session.state
        )
        await self._apply_command_context(
            base_context=context_snapshot,
            updated_context=command.updated_context,
            base_revision=revision_snapshot,
        )
        await self._execute_command(command, base_context=context_snapshot)

    async def _handle_power_off_transition(self) -> None:
        """ONからOFFへの遷移を一度だけ処理する。"""
        self.logger.info("Switch電源OFFを検出、次の電源ONを待機します")
        self._phase_handlers.cancel_background_tasks()
        if self._session.state in (RecordState.RECORDING, RecordState.PAUSED):
            await self._session.cancel()
            base_context, _ = await self._snapshot_context()
            await self._sync_context_from_service(base_context=base_context)
        self._frame_processor.publish_power_off_detected(final=True)
        self.power_off_count += 1

    async def _handle_capture_disconnect_transition(self) -> None:
        """デバイス切断をOFFイベントに変換せず、録画だけ安全に止める。"""
        if self._power_monitor.state is SwitchPowerState.CAPTURE_DISCONNECTED:
            return
        self._power_monitor = self._power_monitor.disconnect()
        self._apply_capture_interval_for_power_state()
        self.logger.warning("キャプチャーデバイス切断を検出しました")
        self.last_phase = None
        await self._refresh_audio_health_for_power_state()
        self._phase_handlers.cancel_background_tasks()
        if self._session.state in (RecordState.RECORDING, RecordState.PAUSED):
            await self._session.cancel()
            base_context, _ = await self._snapshot_context()
            await self._sync_context_from_service(base_context=base_context)

    async def _refresh_audio_health_for_power_state(self) -> None:
        """ARMED時だけ音声復旧と文字起こし準備を開始する。"""
        await self._cancel_audio_preparation()
        if self._power_monitor.state is not SwitchPowerState.ARMED:
            try:
                await self._session.check_audio_health()
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "Switch電源状態変更後のOBS音声確認に失敗しました",
                    power_state=self._power_monitor.state.value,
                    error=str(exc),
                )
            return
        self._audio_preparation_task = asyncio.create_task(
            self._prepare_audio_for_power_on()
        )

    async def _prepare_audio_for_power_on(self) -> None:
        audio_result, transcription_result = await asyncio.gather(
            self._session.check_audio_health(),
            self._session.prepare_transcription(),
            return_exceptions=True,
        )
        if isinstance(audio_result, Exception):
            self.logger.warning(
                "Switch電源ON後のOBS音声確認に失敗しました",
                error=str(audio_result),
            )
        if isinstance(transcription_result, Exception):
            self.logger.warning(
                "Switch電源ON後の文字起こし準備に失敗しました",
                error=str(transcription_result),
            )

    async def _cancel_audio_preparation(self) -> None:
        task = self._audio_preparation_task
        self._audio_preparation_task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def _apply_capture_interval_for_power_state(self) -> None:
        """ON待機・切断中だけ実キャプチャを抑え、ARMEDでは戻す。"""
        interval_seconds = CAPTURE_INTERVAL_BY_POWER_STATE[
            self._power_monitor.state
        ]
        if interval_seconds is None:
            return
        self._capture_producer.set_capture_interval(interval_seconds)

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
        await self._drain_weapon_detection_before_stop()

        async def get_result_frame() -> Frame | None:
            return self._context.result_frame

        try:
            await self._session.stop(get_result_frame)
        finally:
            self._phase_handlers.cancel_background_tasks()

    async def _drain_weapon_detection_before_stop(self) -> None:
        base_context, revision = await self._snapshot_context()
        updated_context = (
            await self._phase_handlers.drain_weapon_detection_completed(
                base_context
            )
        )
        # result_frame には numpy.ndarray が入るため、値比較は行わない。
        # no-op のときは同一インスタンスが返る前提で参照比較する。
        if updated_context is base_context:
            return

        await self._apply_command_context(
            base_context=base_context,
            updated_context=updated_context,
            base_revision=revision,
        )
        self._session.update_context(self._context)

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

    async def _sync_context_if_state_changed(self) -> bool:
        """録画停止への遷移を検知してコンテキストを同期する。

        Returns:
            同期した場合 True
        """
        current_state = self._session.state
        if self._last_record_state == current_state:
            return False
        synced = False
        if current_state is RecordState.STOPPED:
            self._phase_handlers.cancel_background_tasks()
            base_context, _ = await self._snapshot_context()
            await self._sync_context_from_service(base_context=base_context)
            synced = True
        self._last_record_state = current_state
        return synced

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
                    current_context.metadata,
                    combined_updates,
                )
            )
            manual_fields = current_context.manual_fields.union(applied_fields)
            if updated_metadata.result is None:
                result_fields = BATTLE_METADATA_FIELDS | SALMON_METADATA_FIELDS
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

    async def _apply_replay_bootstrap(self) -> None:
        if self._replay_bootstrap_resolver is None:
            return

        bootstrap = self._replay_bootstrap_resolver.resolve()
        if bootstrap is None:
            return
        if bootstrap.phase not in {"matching", "in_game"}:
            self.logger.warning(
                "未対応の replay bootstrap phase を無視します",
                phase=bootstrap.phase,
            )
            return

        game_mode = bootstrap.game_mode or self._context.metadata.game_mode
        metadata = RecordingMetadata(
            game_mode=self._resolve_bootstrap_game_mode(game_mode),
            started_at=datetime.now(),
        )
        context = RecordingContext(metadata=metadata)

        async with self._context_lock:
            self._context = context
            self._context_revision += 1

        self._session.update_context(context)
        if bootstrap.phase == "in_game":
            await self._session.start()
            async with self._context_lock:
                self._context = self._session.context
                self._context_revision += 1

        self.logger.info(
            "replay bootstrap を適用しました",
            phase=bootstrap.phase,
            game_mode=metadata.game_mode.name,
        )

    @staticmethod
    def _resolve_bootstrap_game_mode(game_mode: GameMode | None) -> GameMode:
        return game_mode or GameMode.BATTLE

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
            and not context.weapon_detection_done
            and context.weapon_detection_attempts == 0
            and context.weapon_best_scores is None
            and not context.rate_candidates
        )
