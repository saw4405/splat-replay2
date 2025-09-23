import asyncio
import datetime
import time
from typing import Awaitable, Callable, TypeVar, cast

import numpy as np
from structlog.stdlib import BoundLogger

from splat_replay.application.events.types import EventTypes
from splat_replay.application.interfaces import (
    CapturePort,
    EventPublisher,
    FramePublisher,
    RecorderStatus,
    RecorderWithTranscriptionPort,
    VideoAssetRepositoryPort,
)
from splat_replay.application.services.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.application.services.publisher_worker import PublisherWorker
from splat_replay.application.services.recording_context import (
    RecordingContext,
    SessionPhase,
)
from splat_replay.domain.models import Frame, GameMode, RecordingMetadata
from splat_replay.domain.services import (
    FrameAnalyzer,
    RecordEvent,
    RecordState,
    StateMachine,
)

T = TypeVar("T")

# ================================================================
# 定数 (マジックナンバー排除)
# ================================================================
POWER_OFF_CHECK_INTERVAL = 5.0
POWER_OFF_COUNT_THRESHOLD = 3
EARLY_ABORT_WINDOW_SECONDS = 60
MAX_RECORDING_SECONDS = 600
CONTROL_QUEUE_DRAIN_LIMIT = 20
FRAME_QUEUE_MAXSIZE = 3
PUBLISH_QUEUE_MAXSIZE = 200
FRAME_GET_TIMEOUT = 0.1
FRAME_DEVICE_RETRY_SLEEP = 0.005
FRAME_QUEUE_PUT_TIMEOUT = 0.001
PUBLISHER_LOOP_IDLE = 0.01
WELCOME_MESSAGE = "🎮🎮🎮 Let's play! 🎮🎮🎮"


class AutoRecorder:
    EventTypes = EventTypes
    EARLY_ABORT_WINDOW_SECONDS = EARLY_ABORT_WINDOW_SECONDS
    MAX_RECORDING_SECONDS = MAX_RECORDING_SECONDS

    def __init__(
        self,
        state_machine: StateMachine,
        capture: CapturePort,
        analyzer: FrameAnalyzer,
        recorder: RecorderWithTranscriptionPort,
        asset_repository: VideoAssetRepositoryPort,
        logger: BoundLogger,
        publisher: EventPublisher,
        frame_publisher: FramePublisher,
    ):
        self.sm = state_machine
        self.capture = capture
        self.analyzer = analyzer
        self.recorder = recorder
        self.asset_repository = asset_repository
        self.logger = logger
        self.recorder.add_status_listener(self._on_recorder_status_change)
        self._publisher = publisher
        self._frame_publisher = frame_publisher
        self.metadata = RecordingMetadata()  # backward compat reference
        self._ctx = RecordingContext(self.metadata)
        self._stop_event = asyncio.Event()
        self._control_queue: asyncio.Queue[tuple[str, dict[str, object]]] = (
            asyncio.Queue(maxsize=100)
        )  # 制御は多くても 100
        # サブコンポーネントへ委譲
        self._capture_producer = FrameCaptureProducer(
            capture,
            frame_publisher,
            queue_maxsize=FRAME_QUEUE_MAXSIZE,
            device_retry_sleep=FRAME_DEVICE_RETRY_SLEEP,
            queue_put_timeout=FRAME_QUEUE_PUT_TIMEOUT,
        )
        self._publisher_worker = PublisherWorker(
            publisher,
            frame_publisher,
            queue_maxsize=PUBLISH_QUEUE_MAXSIZE,
            idle_sleep=PUBLISHER_LOOP_IDLE,
        )
        # フレーム単位解析キャッシュ (name, args) -> result
        self._analysis_cache: dict[tuple[str, tuple[object, ...]], object] = {}

        self.last_phase: str | None = None

    # ================================================================
    # 内部: 解析結果キャッシュユーティリティ (フレーム単位)
    # ================================================================

    async def _cached_call(
        self, func: Callable[..., Awaitable[T]], *args: object
    ) -> T:
        """同一フレーム内での analyzer.* の重複呼び出しをキャッシュする。

        フレーム毎に execute ループで cache をクリアするため、キーには
        Frame オブジェクト自体を含めない (含める必要がない)。
        """
        key_parts: list[object] = []
        for a in args:
            # ndarray (Frame) はキャッシュキーに含めない (フレーム毎クリア)
            if isinstance(a, np.ndarray):
                continue
            key_parts.append(a)
        # qualname で衝突回避 (同名関数別実装対策)
        key = (
            getattr(func, "__qualname__", func.__name__),
            tuple(key_parts),
        )
        if key in self._analysis_cache:
            return cast(T, self._analysis_cache[key])
        result = await func(*args)
        self._analysis_cache[key] = result
        return result

    # 小ユーティリティ
    def _game_mode(self) -> GameMode:
        return self._ctx.metadata.game_mode

    # 時刻ユーティリティ (テスト差し替え容易化)
    def _now_dt(self) -> datetime.datetime:
        return datetime.datetime.now()

    def _now_ts(self) -> float:
        return time.time()

    # ================================================================
    # 公開API (外部から呼び出される操作)
    # ================================================================
    async def execute(self) -> bool:
        self.logger.info("自動録画開始")
        detected_power_off = False
        try:
            if self._stop_event.is_set():
                self._stop_event.clear()
            await self.recorder.setup()
            self.capture.setup()

            # Start background workers
            self._publisher_worker.start()
            self._capture_producer.start()

            self.logger.info(WELCOME_MESSAGE)
            await self._publish_operation_status(WELCOME_MESSAGE)
            off_count = 0
            last_check = 0.0
            while not self._stop_event.is_set():
                # 先に制御コマンドを処理（過度ループ抑制のため少量）
                await self._process_control_queue()

                # 非同期にフレームをキューから取得（なければ短時間待機）
                frame = await self._acquire_frame(timeout=FRAME_GET_TIMEOUT)
                if frame is None:
                    # フレーム未到来。CPU スピン緩和のため譲歩。
                    await asyncio.sleep(0)
                    continue

                # このフレーム内の解析結果キャッシュ初期化
                self._analysis_cache.clear()

                (
                    off_count,
                    last_check,
                    detected_power_off,
                ) = await self._check_power_off(frame, off_count, last_check)
                if detected_power_off:
                    self.logger.info("電源OFFを検出、録画を停止")
                    await self._publish_operation_status(
                        "電源OFFを検出したため、自動録画を停止します。"
                    )
                    # EventBus へ通知
                    self._publisher_worker.enqueue_event(
                        EventTypes.POWER_OFF_DETECTED, {}
                    )
                    break

                phase = self._ctx.phase(self.sm.state)
                if self.last_phase != phase:
                    self.logger.info(
                        f"フェーズが変更されました: {self.last_phase} -> {phase}"
                    )
                    self.last_phase = phase

                if self.sm.state is RecordState.PAUSED:
                    await self._process_paused_state(frame)
                elif phase == SessionPhase.STANDBY:
                    await self._process_standby(frame)
                elif phase == SessionPhase.MATCHING:
                    await self._process_matching(frame)
                elif phase == SessionPhase.IN_GAME:
                    await self._process_in_game(frame)
                elif phase == SessionPhase.POST_FINISH:
                    await self._process_post_finish(frame)
                elif phase == SessionPhase.RESULT:
                    await self._process_result(frame)
                else:
                    self.logger.warning("未知のフェーズ", phase=phase)

        except Exception as e:
            self.logger.error("自動録画中にエラーが発生しました", error=str(e))

        finally:
            if self.sm.state in (RecordState.RECORDING, RecordState.PAUSED):
                await self.cancel()
            # Stop background workers
            self._capture_producer.stop()
            self._publisher_worker.stop()
            self.capture.teardown()
            await self.recorder.teardown()
            self.logger.info("自動録画終了")
            if detected_power_off:
                # 念のため終了時にも (重複でも問題無いクライアント側で抑制可)
                self._publisher_worker.enqueue_event(
                    EventTypes.POWER_OFF_DETECTED, {"final": True}
                )

        return detected_power_off

    async def start(self) -> None:
        if self.sm.state is not RecordState.STOPPED:
            self.logger.warning("録画は既に開始されています。")
            return
        self._ctx.battle_started_at = time.time()
        await self.sm.handle(RecordEvent.START)
        await self.recorder.start()
        self._publisher_worker.enqueue_event(
            EventTypes.RECORDER_STATE, {"state": "STARTED"}
        )

    async def pause(self) -> None:
        if self.sm.state is not RecordState.RECORDING:
            self.logger.warning("録画中ではありません。")
            return
        await self.sm.handle(RecordEvent.PAUSE)
        await self.recorder.pause()
        self._publisher_worker.enqueue_event(
            EventTypes.RECORDER_STATE, {"state": "PAUSED"}
        )

    async def resume(self) -> None:
        if self.sm.state is not RecordState.PAUSED:
            self.logger.warning("録画は一時停止中ではありません。")
            return
        await self.sm.handle(RecordEvent.RESUME)
        await self.recorder.resume()
        self._publisher_worker.enqueue_event(
            EventTypes.RECORDER_STATE, {"state": "RECORDING"}
        )

    async def cancel(self) -> None:
        await self.sm.handle(RecordEvent.STOP)
        await self.recorder.cancel()
        self._publisher_worker.enqueue_event(
            EventTypes.RECORDER_STATE, {"state": "CANCELLED"}
        )
        await self._reset()

    async def stop(self) -> None:
        try:
            if self.sm.state is RecordState.STOPPED:
                self.logger.warning("録画されていません。")
                return

            await self.sm.handle(RecordEvent.STOP)
            video, srt = await self.recorder.stop()
            self.logger.info("録画を停止", video=str(video))
            self._publisher_worker.enqueue_event(
                EventTypes.RECORDER_STATE, {"state": "STOPPED"}
            )

            if video is None:
                self.logger.error("録画に失敗しました。")
                return

            if self._ctx.result_frame is None:
                self.logger.error("結果フレームが設定されていません。")
                return

            self.metadata.result = await self.analyzer.extract_session_result(
                self._ctx.result_frame, self.metadata.game_mode
            )
            self.logger.info(
                "バトル結果を検出", result=str(self.metadata.result)
            )

            if self.metadata.started_at is None:
                self.logger.error("マッチング開始時刻が設定されていません。")
                return

            asset = self.asset_repository.save_recording(
                video, srt, self._ctx.result_frame, self.metadata
            )
            self.logger.info(
                "録画終了",
                video=str(asset.video),
                start_at=self.metadata.started_at,
            )
        finally:
            await self._reset()

    def force_stop_loop(self) -> None:
        self._stop_event.set()

    def command_handlers(self) -> dict[str, Callable[[], Awaitable[object]]]:
        """コマンド名 -> 非同期ハンドラ のマッピングを返す。

        インフラ層 (DI) が CommandBus へ登録するために利用し、
        アプリ層はバス実装に依存しない。
        """

        async def _get_metadata() -> RecordingMetadata:
            return self.metadata

        async def _start() -> None:
            await self.start()

        async def _pause() -> None:
            await self.pause()

        async def _resume() -> None:
            await self.resume()

        async def _stop() -> None:
            await self.stop()

        async def _cancel() -> None:
            await self.cancel()

        return {
            "recorder.get_metadata": _get_metadata,
            "recorder.start": _start,
            "recorder.pause": _pause,
            "recorder.resume": _resume,
            "recorder.stop": _stop,
            "recorder.cancel": _cancel,
        }

    # ================================================================
    # イベントハンドラ / 状態同期
    # ================================================================
    async def handle_record_state_changed(self, state: RecorderStatus) -> None:
        """Recorder 実装が通知する状態と StateMachine の齟齬を検出。"""
        expected: dict[str, RecordState] = {
            "started": RecordState.RECORDING,
            "stopped": RecordState.STOPPED,
            "paused": RecordState.PAUSED,
            "resumed": RecordState.RECORDING,
        }
        target = expected.get(state)
        if target is None:
            self.logger.warning("未知のレコーダ状態", recorder=state)
            return
        if target != self.sm.state:
            self.logger.error(
                "状態が一致しません。",
                recorder=state,
                expected=target.name,
                actual=self.sm.state.name,
            )

    # ================================================================
    # 内部ユーティリティ (状態/通知)
    # ================================================================
    async def _on_recorder_status_change(self, state: RecorderStatus) -> None:
        """OBS 由来の録画状態変化を GUI/StateMachine に反映する。"""
        status_to_state: dict[str, RecordState] = {
            "started": RecordState.RECORDING,
            "stopped": RecordState.STOPPED,
            "paused": RecordState.PAUSED,
            "resumed": RecordState.RECORDING,
        }
        target: RecordState | None = status_to_state.get(state)
        if target is None:
            self.logger.warning("未知のRecorder状態", recorder=state)
            return
        if target != self.sm.state:
            transition: dict[tuple[RecordState, RecordState], RecordEvent] = {
                (
                    RecordState.STOPPED,
                    RecordState.RECORDING,
                ): RecordEvent.START,
                (RecordState.RECORDING, RecordState.PAUSED): RecordEvent.PAUSE,
                (
                    RecordState.PAUSED,
                    RecordState.RECORDING,
                ): RecordEvent.RESUME,
                (RecordState.RECORDING, RecordState.STOPPED): RecordEvent.STOP,
                (RecordState.PAUSED, RecordState.STOPPED): RecordEvent.STOP,
            }
            evt: RecordEvent | None = transition.get((self.sm.state, target))
            if evt is not None:
                await self.sm.handle(evt)
            else:
                self.logger.warning(
                    "Recorder状態とStateMachine遷移の不一致",
                    recorder=state,
                    current=self.sm.state.name,
                    target=target.name,
                )
        # GUI へ即反映
        self._publisher_worker.enqueue_event(
            EventTypes.RECORDER_STATE, {"state": target.name}
        )

    async def _publish_operation_status(self, state: str) -> None:
        self._publisher_worker.enqueue_event(
            EventTypes.RECORDER_OPERATION, {"message": state}
        )

    async def _reset(self) -> None:
        """録画の状態をリセットする。"""
        self._ctx.reset()
        await self._publish_operation_status(WELCOME_MESSAGE)

    # ================================================================
    # 制御キュー / フレーム取得
    # ================================================================
    async def _process_control_queue(self) -> None:
        # 連続し過ぎないよう 20 コマンド/ループ上限
        handlers: dict[str, Callable[[], Awaitable[None]]] = {
            "start": self.start,
            "pause": self.pause,
            "resume": self.resume,
            "stop": self.stop,
            "cancel": self.cancel,
        }
        for _ in range(CONTROL_QUEUE_DRAIN_LIMIT):
            if self._control_queue.empty():
                break
            cmd, kwargs = await self._control_queue.get()
            handler = handlers.get(cmd)
            if handler is None:
                self.logger.warning("未知の制御コマンド", cmd=cmd)
                continue
            try:
                await handler()
            except Exception as e:
                self.logger.error(
                    "制御コマンド処理エラー", cmd=cmd, error=str(e)
                )

    async def _acquire_frame(self, timeout: float) -> Frame | None:
        """Captureスレッドから渡されたフレームを取得する。

        - `queue.Queue` はスレッド間通信用（asyncio.Queue は未対応）
        - ブロッキングは `to_thread` へ委譲し、イベントループを塞がない
        """
        return await asyncio.to_thread(
            self._capture_producer.get_frame, timeout
        )

    # ================================================================
    # 解析 / 状態遷移ハンドラ
    # ================================================================
    async def _check_power_off(
        self, frame: Frame, off_count: int, last_check: float
    ) -> tuple[int, float, bool]:
        now = time.time()
        if now - last_check < POWER_OFF_CHECK_INTERVAL:
            return off_count, last_check, False

        last_check = now
        if await self.analyzer.detect_power_off(frame):
            off_count += 1
            self.logger.info("電源OFFを検出", count=off_count)
        else:
            off_count = 0

        detected = off_count >= POWER_OFF_COUNT_THRESHOLD
        return off_count, last_check, detected

    # ================================================================
    # フェーズ別処理 (インライン実装)
    # ================================================================
    async def _process_standby(self, frame: Frame) -> None:
        md = self.metadata
        if await self._cached_call(self.analyzer.detect_match_select, frame):
            game_mode = await self._cached_call(
                self.analyzer.extract_game_mode, frame
            )
            if game_mode is not None and game_mode != md.game_mode:
                md.game_mode = game_mode
                self.logger.info("ゲームモード取得", mode=str(md.game_mode))

            rate = await self._cached_call(
                self.analyzer.extract_rate, frame, md.game_mode
            )
            if rate is not None and (
                not isinstance(rate, type(md.rate)) or rate != md.rate
            ):
                md.rate = rate
                self.logger.info("レート取得", rate=str(rate))

        if await self._cached_call(self.analyzer.detect_matching_start, frame):
            self.logger.info("マッチング開始を検出")
            await self._publish_operation_status(
                "マッチング開始を検出しました。"
            )
            md.started_at = self._now_dt()

    async def _process_matching(self, frame: Frame) -> None:
        md = self.metadata
        if await self._cached_call(
            self.analyzer.detect_schedule_change, frame
        ):
            self.logger.info("スケジュール変更を検出、情報をリセット")
            await self._publish_operation_status(
                "スケジュール変更を検出しました。"
            )
            await self._reset()
            return
        if await self._cached_call(
            self.analyzer.detect_session_start, frame, md.game_mode
        ):
            self.logger.info("バトル開始を検出")
            await self._publish_operation_status(
                "バトル開始を検出したため、録画を開始します。"
            )
            await self.start()
            self._publisher_worker.enqueue_event(
                EventTypes.RECORDER_MATCH, {"event": "battle_started"}
            )

    async def _process_in_game(self, frame: Frame) -> None:
        gm = self._game_mode()
        now = time.time()
        if (
            now - self._ctx.battle_started_at <= EARLY_ABORT_WINDOW_SECONDS
            and await self._cached_call(
                self.analyzer.detect_session_abort, frame, gm
            )
        ):
            self.logger.info("バトル中断を検出したため録画を中止")
            await self._publish_operation_status(
                "バトル中断を検出したため、録画を中止します。"
            )
            await self.cancel()
            return
        if now - self._ctx.battle_started_at >= MAX_RECORDING_SECONDS:
            self.logger.info("録画が10分以上続いたため停止")
            await self._publish_operation_status(
                "録画が10分以上続いたため、録画を停止します。"
            )
            await self.stop()
            return
        if await self._cached_call(
            self.analyzer.detect_session_finish, frame, gm
        ):
            self.logger.info("バトル終了を検出、一時停止")
            await self._publish_operation_status(
                "バトル終了を検出したため、録画を一時停止します。"
            )
            self._ctx.finish = True
            self._ctx.resume_trigger = (
                lambda f: self.analyzer.detect_session_judgement(f, gm)
            )
            await self.pause()
            return
        if await self._cached_call(
            self.analyzer.detect_session_judgement, frame, gm
        ):
            self._ctx.finish = True
            self.logger.info("バトル終了より前にバトル判定を検出")
            await self._publish_operation_status("バトル判定を検出しました。")
            judgement = await self._cached_call(
                self.analyzer.extract_session_judgement, frame, gm
            )
            if judgement is not None and self._ctx.metadata.judgement is None:
                self._ctx.metadata.judgement = judgement
                self.logger.info(
                    "バトルジャッジメント取得", judgement=str(judgement)
                )
            return
        if await self._cached_call(
            self.analyzer.detect_communication_error, frame, gm
        ):
            self.logger.info("通信エラーを検出")
            await self._publish_operation_status(
                "通信エラーを検出したため、録画を中止します。"
            )
            await self.cancel()
            return

    async def _process_post_finish(self, frame: Frame) -> None:
        gm = self._game_mode()
        if self._ctx.metadata.judgement is None and await self._cached_call(
            self.analyzer.detect_session_judgement, frame, gm
        ):
            self.logger.info("バトル判定を検出")
            await self._publish_operation_status("バトル判定を検出しました。")
            judgement = await self._cached_call(
                self.analyzer.extract_session_judgement, frame, gm
            )
            if judgement is not None and self._ctx.metadata.judgement is None:
                self._ctx.metadata.judgement = judgement
                self.logger.info(
                    "バトルジャッジメント取得", judgement=str(judgement)
                )
            return
        if await self._cached_call(self.analyzer.detect_loading, frame):
            self.logger.info("ローディング画面を検出、一時停止")
            await self._publish_operation_status(
                "ローディング画面を検出したため、録画を一時停止します。"
            )
            self._ctx.resume_trigger = self.analyzer.detect_loading_end
            await self.pause()
            return
        if await self._cached_call(
            self.analyzer.detect_session_result, frame, gm
        ):
            self.logger.info("結果画面を検出")
            await self._publish_operation_status("結果画面を検出しました。")
            self._ctx.result_frame = frame

    async def _process_result(self, frame: Frame) -> None:
        gm = self._game_mode()
        still_result = await self._cached_call(
            self.analyzer.detect_session_result, frame, gm
        )
        if not still_result:
            self.logger.info("結果画面から遷移")
            await self._publish_operation_status(
                "結果画面から遷移したため、録画を停止します。"
            )
            await self.stop()

    async def _process_paused_state(self, frame: Frame) -> None:
        if self._ctx.resume_trigger and await self._ctx.resume_trigger(frame):
            self.logger.info("録画を再開")
            await self._publish_operation_status("録画を再開します。")
            await self.resume()
