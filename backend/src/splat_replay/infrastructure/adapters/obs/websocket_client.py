"""OBS Studio WebSocket通信クライアント。

責務:
- WebSocket接続・切断
- 自動再接続
- リクエスト送信
- イベント受信
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any, Awaitable, Callable

from obswsc.client import ObsWsClient
from obswsc.data import Event, Request, Response1, Response2
from structlog.stdlib import BoundLogger

from splat_replay.domain.exceptions import DeviceError

Response = Response1 | Response2
EventCallback = Callable[[Event], Awaitable[None]]


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

        # reg_event_cb は Awaitable を期待するが、実際にはコルーチン関数を受け取る設計
        self._client.reg_event_cb(_wrapper, event_type)  # type: ignore[arg-type]

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
                await self._client.connect()
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
        self._logger.info("OBS WebSocket切断完了")

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
                    await self._client.connect()
                    self._is_connected = True
                    self._logger.info("OBS WebSocket 再接続完了")
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
        self, request_type: str, idempotent: bool = False
    ) -> Response1:
        """リクエストを送信。

        接続が切れている場合は自動再接続。
        冪等なリクエストの場合は1回リトライ。

        Args:
            request_type: リクエストタイプ（例: "StartRecord"）
            idempotent: 冪等性（True = 複数回実行しても安全）

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
                response = await self._client.request(Request(request_type))
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
