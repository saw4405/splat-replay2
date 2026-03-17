import asyncio
from typing import Awaitable, Callable, Iterable

from splat_replay.application.interfaces import (
    CapturePort,
    ClockPort,
    DomainEventPublisher,
    EventBusPort,
    EventPublisher,
    EventSubscription,
    FramePublisher,
    LoggerPort,
    RecorderStatus,
    RecorderWithTranscriptionPort,
    VideoAssetRepositoryPort,
    WeaponRecognitionPort,
)
from splat_replay.application.services.recording.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.application.services.recording.frame_processing_service import (
    FrameProcessingService,
)
from splat_replay.application.services.recording.phase_handler_registry import (
    PhaseHandlerRegistry,
)
from splat_replay.application.services.common.battle_history_service import (
    BattleHistoryService,
)
from splat_replay.application.services.recording.publisher_worker import (
    PublisherWorker,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.weapon_detection_service import (
    DETECTION_WINDOW_SECONDS,
    WeaponDetectionService,
)
from splat_replay.application.services.recording.recording_session_service import (
    RecordingSessionService,
)
from splat_replay.domain.events import DomainEvent
from splat_replay.domain.models import RecordingMetadata
from splat_replay.domain.services import (
    FrameAnalyzer,
    RecordState,
    StateMachine,
)

# ================================================================
# 定数 (マジックナンバー排除)
# ================================================================
POWER_OFF_CHECK_INTERVAL = 5.0
POWER_OFF_COUNT_THRESHOLD = 3
EARLY_ABORT_WINDOW_SECONDS = 60
MAX_RECORDING_SECONDS = 600
CONTROL_QUEUE_DRAIN_LIMIT = 20
FRAME_QUEUE_MAXSIZE = 1
PUBLISH_QUEUE_MAXSIZE = 200
FRAME_DEVICE_RETRY_SLEEP = 0.005
FRAME_QUEUE_PUT_TIMEOUT = 0.001
PUBLISHER_LOOP_IDLE = 0.01
WELCOME_MESSAGE = "🎮🎮🎮 Let's play! 🎮🎮🎮"


class AutoRecorder:
    EARLY_ABORT_WINDOW_SECONDS = EARLY_ABORT_WINDOW_SECONDS
    MAX_RECORDING_SECONDS = MAX_RECORDING_SECONDS

    def __init__(
        self,
        state_machine: StateMachine,
        capture: CapturePort,
        analyzer: FrameAnalyzer,
        recorder: RecorderWithTranscriptionPort,
        asset_repository: VideoAssetRepositoryPort,
        logger: LoggerPort,
        weapon_recognizer: WeaponRecognitionPort,
        publisher: EventPublisher,
        frame_publisher: FramePublisher,
        domain_publisher: DomainEventPublisher,
        battle_history_service: BattleHistoryService,
        weapon_detection_window_seconds: float = DETECTION_WINDOW_SECONDS,
        clock: ClockPort | None = None,
    ):
        self.logger = logger
        self._stop_event = asyncio.Event()
        self._control_queue: asyncio.Queue[tuple[str, dict[str, object]]] = (
            asyncio.Queue(maxsize=100)
        )

        # Phase 4 Step 2: サブコンポーネントの初期化
        self.capture = capture
        self.metadata = RecordingMetadata()
        self._ctx = RecordingContext(self.metadata)

        # ワーカーの初期化
        self._capture_producer = FrameCaptureProducer(
            capture,
            frame_publisher,
            queue_maxsize=FRAME_QUEUE_MAXSIZE,
            device_retry_sleep=FRAME_DEVICE_RETRY_SLEEP,
            queue_put_timeout=FRAME_QUEUE_PUT_TIMEOUT,
        )
        self._publisher_worker = PublisherWorker(
            publisher,
            queue_maxsize=PUBLISH_QUEUE_MAXSIZE,
            idle_sleep=PUBLISHER_LOOP_IDLE,
        )

        # Phase 4 Step 2: サービスの初期化
        self._session = RecordingSessionService(
            state_machine=state_machine,
            recorder=recorder,
            asset_repository=asset_repository,
            analyzer=analyzer,
            logger=logger,
            context=self._ctx,
            domain_publisher=domain_publisher,
            battle_history_service=battle_history_service,
            clock=clock,
        )

        self._frame_processor = FrameProcessingService(
            capture_producer=self._capture_producer,
            analyzer=analyzer,
            logger=logger,
            domain_publisher=domain_publisher,
        )

        # Phase 4 Step 1: フェーズハンドラの導入
        # PublisherWorker を EventBusPort プロトコルに適合させるアダプタ
        class EventBusAdapter:
            """PublisherWorker を EventBusPort プロトコルに適合させる。"""

            def __init__(
                self, worker: PublisherWorker, dp: DomainEventPublisher
            ):
                self._worker = worker
                self._domain_publisher = dp

            def publish(
                self, type_: str, payload: dict[str, object] | None = None
            ) -> None:
                """レガシーイベントを publish する。"""
                self._worker.enqueue_event(type_, payload or {})

            def publish_domain_event(self, event: DomainEvent) -> None:
                """ドメインイベントを publish する。"""
                self._domain_publisher.publish_domain_event(event)

            def subscribe(
                self, event_types: Iterable[str] | None = None
            ) -> EventSubscription:
                """subscribe は未実装（ハンドラでは使用しない）。"""
                raise NotImplementedError(
                    "subscribe is not supported in handlers"
                )

        # EventBusPort 型を満たすアダプタ
        event_bus_adapter: EventBusPort = EventBusAdapter(  # type: ignore[assignment]
            self._publisher_worker, domain_publisher
        )
        weapon_detection_service = WeaponDetectionService(
            recognizer=weapon_recognizer,
            logger=logger,
            event_bus=event_bus_adapter,
            detection_window_seconds=weapon_detection_window_seconds,
            clock=clock,
        )

        self._phase_handlers = PhaseHandlerRegistry(
            analyzer=analyzer,
            logger=logger,
            event_bus=event_bus_adapter,
            weapon_detection_service=weapon_detection_service,
            clock=clock,
        )

    # ================================================================
    # Internal components access (for AutoRecordingUseCase)
    # ================================================================
    @property
    def session_service(self) -> RecordingSessionService:
        return self._session

    @property
    def frame_processor(self) -> FrameProcessingService:
        return self._frame_processor

    @property
    def phase_handlers(self) -> PhaseHandlerRegistry:
        return self._phase_handlers

    @property
    def context(self) -> RecordingContext:
        return self._ctx

    @property
    def capture_producer(self) -> FrameCaptureProducer:
        return self._capture_producer

    @property
    def publisher_worker(self) -> PublisherWorker:
        return self._publisher_worker

    # ================================================================
    # Phase 4 Step 2: PhaseHandlerRegistry へ渡すコールバック
    # ================================================================
    async def _start_recording(self) -> None:
        """録画開始（PhaseHandlerRegistry から呼ばれる）。"""
        await self._session.start()

    async def _pause_recording(self) -> None:
        """録画一時停止（PhaseHandlerRegistry から呼ばれる）。"""
        await self._session.pause()

    async def _resume_recording(self) -> None:
        """録画再開（PhaseHandlerRegistry から呼ばれる）。"""
        await self._session.resume()

    async def _stop_recording(self) -> None:
        """録画停止（PhaseHandlerRegistry から呼ばれる）。"""
        await self._session.stop(self._frame_processor.acquire_frame)

    async def _cancel_recording(self) -> None:
        """録画中止（PhaseHandlerRegistry から呼ばれる）。"""
        await self._session.cancel()

    async def _reset_metadata(self) -> None:
        """メタデータリセット（PhaseHandlerRegistry から呼ばれる）。"""
        await self._session.reset()

    # ================================================================
    # 公開 API (外部から呼び出される操作) - SessionService に委譲
    # ================================================================
    async def start(self) -> None:
        """録画を開始する。"""
        await self._session.start()

    async def pause(self) -> None:
        """録画を一時停止する。"""
        await self._session.pause()

    async def resume(self) -> None:
        """録画を再開する。"""
        await self._session.resume()

    async def cancel(self) -> None:
        """録画を中止する（ファイル削除）。"""
        await self._session.cancel()

    async def stop(self) -> None:
        """録画を停止し、ビデオアセットを保存する。"""
        await self._session.stop(self._frame_processor.acquire_frame)

    def get_state(self) -> str:
        """現在の録画状態を取得する。

        Returns:
            状態文字列（"STOPPED", "RECORDING", "PAUSED"）
        """
        from splat_replay.domain.services.state_machine import RecordState

        state_map = {
            RecordState.STOPPED: "STOPPED",
            RecordState.RECORDING: "RECORDING",
            RecordState.PAUSED: "PAUSED",
        }
        return state_map.get(self._session.state, "UNKNOWN")

    # ================================================================
    # コマンドハンドラ（CommandBus 登録用）
    # ================================================================
    def command_handlers(self) -> dict[str, Callable[[], Awaitable[object]]]:
        """コマンド名 -> 非同期ハンドラ のマッピングを返す。

        インフラ層 (DI) が CommandBus へ登録するために利用し、
        アプリ層はバス実装に依存しない。
        """

        async def _get_metadata() -> RecordingMetadata:
            return self._session.metadata

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
        if target != self._session.state:
            self.logger.error(
                "状態が一致しません。",
                recorder=state,
                expected=target.name,
                actual=self._session.state.name,
            )

    # ================================================================
    # 内部ユーティリティ (状態/通知)
    # ================================================================
    # ================================================================
    # 制御コマンド処理（Phase 4 Step 3: UseCase に移動予定）
    # ================================================================
    async def _process_control_queue(self) -> None:
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

    # ================================================================
    # 内部ヘルパー（Phase 4 Step 2: 一部は Service に移動済み）
    # ================================================================
