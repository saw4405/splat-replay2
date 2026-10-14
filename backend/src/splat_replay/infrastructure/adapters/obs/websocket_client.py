"""OBS Studio WebSocket通信クライアント。

責務:
- WebSocket接続・切断
- 自動再接続
- リクエスト送信
- イベント受信
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Iterable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from obswsc.client import ObsWsClient
from obswsc.data import Event, Request, Response1, Response2
from obswsc.enums import EventSubscription
from structlog.stdlib import BoundLogger

from splat_replay.domain.exceptions import DeviceError

Response = Response1 | Response2
EventCallback = Callable[[Event], Awaitable[None]]


@dataclass(frozen=True)
class InputVolumeMeterSample:
    event_count: int
    numeric_mul_samples: int
    numeric_db_samples: int
    peak_mul: float | None
    peak_db: float | None


@dataclass
class _InputVolumeMeterAccumulator:
    event_count: int = 0
    numeric_mul_samples: int = 0
    numeric_db_samples: int = 0
    peak_mul: float | None = None
    peak_db: float | None = None

    def add(self, item: dict[str, Any]) -> None:
        self.event_count += 1
        peak_mul = _extract_peak_number(item.get("inputLevelsMul"))
        peak_db = _extract_peak_number(item.get("inputLevelsDb"))
        if peak_mul is not None:
            self.numeric_mul_samples += 1
            self.peak_mul = (
                peak_mul
                if self.peak_mul is None
                else max(self.peak_mul, peak_mul)
            )
        if peak_db is not None:
            self.numeric_db_samples += 1
            self.peak_db = (
                peak_db if self.peak_db is None else max(self.peak_db, peak_db)
            )

    def freeze(self) -> InputVolumeMeterSample:
        return InputVolumeMeterSample(
            event_count=self.event_count,
            numeric_mul_samples=self.numeric_mul_samples,
            numeric_db_samples=self.numeric_db_samples,
            peak_mul=self.peak_mul,
            peak_db=self.peak_db,
        )


def _extract_peak_number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return None
    peak: float | None = None
    for item in value:
        item_peak = _extract_peak_number(item)
        if item_peak is not None:
            peak = item_peak if peak is None else max(peak, item_peak)
    return peak


class OBSWebSocketClient:
    """OBS WebSocket通信の管理。

    責務:
    - WebSocket接続・切断
    - 自動再接続（指数バックオフ）
    - リクエスト送信（自動リトライ）
    - イベントコールバック管理
    """

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        logger: BoundLogger,
        on_reconnect: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """初期化。

        Args:
            host: WebSocketホスト
            port: WebSocketポート
            password: WebSocketパスワード
            logger: ロガー
        """
        self._logger = logger
        self._url = f"ws://{host}:{port}"
        self._password = password
        self._client = ObsWsClient(url=self._url, password=password)
        self._is_connected = False
        self._monitor_task: asyncio.Task[None] | None = None
        self._on_reconnect = on_reconnect
        self._event_callbacks: list[tuple[str, EventCallback]] = []
        self._meter_cleanup_tasks: set[asyncio.Task[None]] = set()

    def update_settings(self, host: str, port: int, password: str) -> None:
        """接続設定を更新。

        Args:
            host: WebSocketホスト
            port: WebSocketポート
            password: WebSocketパスワード
        """
        self._url = f"ws://{host}:{port}"
        self._password = password
        self._client = ObsWsClient(url=self._url, password=password)
        self._is_connected = False
        for event_type, callback in self._event_callbacks:
            self._register_event_callback(event_type, callback)
        self._logger.info("OBS WebSocket設定更新", url=self._url)

    def register_event_callback(
        self, event_type: str, callback: EventCallback
    ) -> None:
        """イベントコールバックを登録。

        Args:
            event_type: イベントタイプ（例: "RecordStateChanged"）
            callback: コールバック関数
        """

        async def _wrapper(event: Event) -> None:
            try:
                await callback(event)
            except Exception as exc:  # pragma: no cover - logging path
                self._logger.warning(
                    "イベントリスナーエラー",
                    event_type=event_type,
                    error=str(exc),
                )

        self._event_callbacks.append((event_type, _wrapper))
        self._register_event_callback(event_type, _wrapper)

    def _register_event_callback(
        self, event_type: str, callback: EventCallback
    ) -> None:
        # reg_event_cb は Awaitable を期待するが、実際にはコルーチン関数を受け取る設計
        self._client.reg_event_cb(callback, event_type)  # type: ignore[arg-type]

    @property
    def is_connected(self) -> bool:
        """接続状態を取得。"""
        return self._is_connected

    async def connect(self) -> None:
        """WebSocketに接続。

        最大5回リトライ。

        Raises:
            DeviceError: 接続失敗時
        """
        self._logger.info("OBS WebSocket接続要求")

        for attempt in range(5):
            try:
                if await self._client.connect() is False:
                    raise ConnectionError("OBS WebSocket connection failed")
                self._is_connected = True
                self._logger.info("OBS WebSocket接続成功")

                # 接続監視タスクを開始
                if self._monitor_task is None or self._monitor_task.done():
                    self._monitor_task = asyncio.create_task(
                        self._monitor_connection()
                    )
                return
            except Exception as exc:
                self._logger.warning(
                    "OBS 接続失敗", error=str(exc), attempt=attempt + 1
                )
                await asyncio.sleep(1)

        self._logger.error("OBS への接続に失敗")
        raise DeviceError(
            "OBS への接続に失敗しました", "OBS_CONNECTION_FAILED"
        )

    async def disconnect(self) -> None:
        """WebSocketから切断。"""
        self._logger.info("OBS WebSocket切断要求")

        # 監視タスクを停止
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            with suppress(Exception):
                await self._monitor_task
            self._monitor_task = None

        # 切断
        self._is_connected = False
        with suppress(Exception):
            await self._client.disconnect()
        await self.drain_meter_cleanup_tasks()
        self._logger.info("OBS WebSocket切断完了")

    async def drain_meter_cleanup_tasks(self) -> None:
        """音量メーター接続の終了taskを期限付きで回収する。"""
        tasks = tuple(self._meter_cleanup_tasks)
        if not tasks:
            return
        _, pending = await asyncio.wait(tasks, timeout=0.5)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.wait(pending, timeout=0.5)

    async def _monitor_connection(self) -> None:
        """接続を監視し、切断時は自動再接続。

        指数バックオフで再接続を試行。
        """
        backoff = 1.0
        max_backoff = 10.0

        while True:
            task: Awaitable[object] | None = getattr(
                self._client, "task", None
            )
            if task is None:
                await asyncio.sleep(0.5)
                continue

            try:
                await task
            except asyncio.CancelledError:
                self._logger.info("接続監視タスク停止")
                return
            except Exception as exc:
                self._logger.warning("OBS 受信ループ異常終了", error=str(exc))

            # 切断を検知したら再接続
            self._is_connected = False
            with suppress(Exception):
                await self._client.disconnect()
            self._logger.warning("OBS WebSocket 切断。再接続します")

            # 再接続ループ（指数バックオフ）
            while True:
                try:
                    if await self._client.connect() is False:
                        raise ConnectionError(
                            "OBS WebSocket connection failed"
                        )
                    self._is_connected = True
                    self._logger.info("OBS WebSocket 再接続完了")
                    if self._on_reconnect is not None:
                        try:
                            await self._on_reconnect()
                        except Exception as exc:  # noqa: BLE001
                            self._logger.warning(
                                "OBS 再接続後セットアップ失敗",
                                error=str(exc),
                            )
                    backoff = 1.0
                    break
                except Exception as exc:
                    self._logger.warning(
                        "OBS 再接続失敗",
                        error=str(exc),
                        delay=f"{backoff:.1f}s",
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(max_backoff, backoff * 1.5)

    async def request(
        self,
        request_type: str,
        idempotent: bool = False,
        request_data: dict[str, object] | None = None,
    ) -> Response1:
        """リクエストを送信。

        接続が切れている場合は自動再接続。
        冪等なリクエストの場合は1回リトライ。

        Args:
            request_type: リクエストタイプ（例: "StartRecord"）
            idempotent: 冪等性（True = 複数回実行しても安全）
            request_data: OBS WebSocket に渡す requestData

        Returns:
            レスポンス

        Raises:
            DeviceError: リクエスト失敗時
        """
        max_attempts = 2 if idempotent else 1

        for attempt in range(max_attempts):
            # 未接続なら再接続
            if not self._is_connected:
                await self.connect()

            try:
                data = request_data if request_data is not None else {}
                response = await self._client.request(
                    Request(request_type, data)
                )
                if isinstance(response, Response2):
                    return response.results[0]
                return response
            except Exception as exc:
                self._logger.warning(
                    "OBS リクエスト失敗",
                    request=request_type,
                    error=str(exc),
                    attempt=attempt + 1,
                )

                # 切断フラグを立てる
                self._is_connected = False
                with suppress(Exception):
                    await self._client.disconnect()

                # リトライ可能な場合は待機
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5)
                    continue

                # リトライ上限到達
                raise DeviceError(
                    f"OBS リクエストに失敗しました: {request_type}",
                    "OBS_REQUEST_FAILED",
                    cause=exc,
                ) from exc

        # ここには到達しないはずだが、型チェック対策
        raise DeviceError(
            f"OBS リクエストが失敗しました: {request_type}",
            "OBS_REQUEST_FAILED",
        )

    async def set_event_subscriptions(self, subscriptions: int) -> None:
        """Update OBS event subscriptions for the active WebSocket session."""
        if not self._is_connected:
            await self.connect()
        await self._client.subscribe(subscriptions)

    async def subscribe_default_events(self) -> None:
        """Restore the default non-high-volume OBS event subscription."""
        await self.set_event_subscriptions(EventSubscription.All.value)

    async def iter_input_volume_meter_windows(
        self, *, window_seconds: float = 1.0
    ) -> AsyncGenerator[dict[str, InputVolumeMeterSample], None]:
        """独立接続から入力別に集計した音量メーター窓を返す。"""
        meter_client = ObsWsClient(url=self._url, password=self._password)
        current_window: dict[str, _InputVolumeMeterAccumulator] = {}
        window_queue: asyncio.Queue[
            dict[str, InputVolumeMeterSample] | Exception
        ] = asyncio.Queue(maxsize=1)
        window_task: asyncio.Task[None] | None = None

        async def _on_meter(event: Event) -> None:
            nonlocal current_window
            inputs = (
                event.event_data.get("inputs") if event.event_data else None
            )
            if not isinstance(inputs, list):
                return
            for item in inputs:
                if not isinstance(item, dict):
                    continue
                input_name = item.get("inputName")
                if isinstance(input_name, str):
                    current_window.setdefault(
                        input_name, _InputVolumeMeterAccumulator()
                    ).add(item)

        meter_client.reg_event_cb(_on_meter, "InputVolumeMeters")  # type: ignore[arg-type]
        try:
            connected = await meter_client.connect()
            if not connected:
                raise DeviceError(
                    "OBS 音量メーター用 WebSocket 接続に失敗しました",
                    "OBS_CONNECTION_FAILED",
                )
            await meter_client.subscribe(
                EventSubscription.All.value
                | EventSubscription.InputVolumeMeters.value
            )
            duration = max(window_seconds, 0.1)

            async def _collect_windows() -> None:
                nonlocal current_window
                try:
                    while True:
                        task = getattr(meter_client, "task", None)
                        if isinstance(task, asyncio.Future):
                            done, _ = await asyncio.wait(
                                {task}, timeout=duration
                            )
                            if done:
                                with suppress(
                                    asyncio.CancelledError, Exception
                                ):
                                    task.result()
                                raise DeviceError(
                                    "OBS 音量メーター接続が切断されました",
                                    "OBS_CONNECTION_FAILED",
                                )
                        else:
                            await asyncio.sleep(duration)
                        completed_window = current_window
                        current_window = {}
                        snapshot = {
                            name: accumulator.freeze()
                            for name, accumulator in completed_window.items()
                        }
                        if window_queue.full():
                            # ponytail: 遅延時は古い窓を1件捨て、最新状態を保つ。
                            window_queue.get_nowait()
                        window_queue.put_nowait(snapshot)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if window_queue.full():
                        window_queue.get_nowait()
                    window_queue.put_nowait(exc)

            window_task = asyncio.create_task(_collect_windows())
            while True:
                window = await window_queue.get()
                if isinstance(window, Exception):
                    raise window
                yield window
        finally:
            if window_task is not None:
                window_task.cancel()
                with suppress(asyncio.CancelledError):
                    await window_task
            cleanup_task = asyncio.create_task(meter_client.disconnect())
            self._meter_cleanup_tasks.add(cleanup_task)
            cleanup_task.add_done_callback(self._on_meter_cleanup_done)
            _, pending = await asyncio.wait({cleanup_task}, timeout=0.5)
            if pending:
                cleanup_task.cancel()

    def _on_meter_cleanup_done(self, task: asyncio.Task[None]) -> None:
        self._meter_cleanup_tasks.discard(task)
        with suppress(asyncio.CancelledError, Exception):
            task.exception()

    async def collect_input_volume_meter_events(
        self, input_name: str, *, sample_duration_seconds: float
    ) -> list[dict[str, Any]]:
        """同じ独立メーターストリームから一窓分を集計する。"""
        windows = self.iter_input_volume_meter_windows(
            window_seconds=sample_duration_seconds
        )
        try:
            window = await anext(windows)
        finally:
            await windows.aclose()
        sample = window.get(input_name)
        if sample is None:
            return []
        return [
            {
                "inputLevelsMul": (
                    [sample.peak_mul] if sample.peak_mul is not None else []
                ),
                "inputLevelsDb": (
                    [sample.peak_db] if sample.peak_db is not None else []
                ),
                "_eventCount": sample.event_count,
                "_numericMulSamples": sample.numeric_mul_samples,
                "_numericDbSamples": sample.numeric_db_samples,
            }
        ]

    async def get_data(self, request_type: str, key: str) -> Any:
        """リクエストを送信してデータを取得。

        Args:
            request_type: リクエストタイプ
            key: レスポンスから取得するキー

        Returns:
            データ（存在しない場合はNone）
        """
        response = await self.request(request_type, idempotent=True)
        if response.res_data is None:
            return None
        return response.res_data.get(key)
