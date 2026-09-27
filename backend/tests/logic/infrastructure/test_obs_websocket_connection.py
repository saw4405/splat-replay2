"""OBS WebSocket 接続ライブラリの失敗戻り値を確認する。"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from unittest.mock import Mock

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.infrastructure.adapters.obs.websocket_client import (
    OBSWebSocketClient,
)


class _ClientStub:
    def __init__(self) -> None:
        self.connect_calls = 0
        self.task: asyncio.Future[None] = (
            asyncio.get_running_loop().create_future()
        )
        self.task.set_result(None)

    async def connect(self) -> bool:
        self.connect_calls += 1
        if self.connect_calls == 1:
            return False
        self.task = asyncio.get_running_loop().create_future()
        return True

    async def disconnect(self) -> None:
        return None


@pytest.mark.asyncio
async def test_initial_connection_retries_false_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OBSWebSocketClient("localhost", 4455, "", Mock(spec=BoundLogger))
    stub = _ClientStub()
    monkeypatch.setattr(client, "_client", stub)

    await client.connect()

    assert stub.connect_calls == 2
    await asyncio.sleep(0)
    await client.disconnect()


@pytest.mark.asyncio
async def test_reconnection_waits_for_success_before_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback_called = asyncio.Event()
    keep_callback_open = asyncio.Event()

    async def on_reconnect() -> None:
        callback_called.set()
        await keep_callback_open.wait()

    client = OBSWebSocketClient(
        "localhost", 4455, "", Mock(spec=BoundLogger), on_reconnect
    )
    stub = _ClientStub()
    monkeypatch.setattr(client, "_client", stub)
    monitor = asyncio.create_task(client._monitor_connection())
    try:
        await asyncio.wait_for(callback_called.wait(), timeout=5)
        assert stub.connect_calls == 2
    finally:
        monitor.cancel()
        with suppress(asyncio.CancelledError):
            await monitor
