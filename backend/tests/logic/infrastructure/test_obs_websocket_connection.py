"""OBS WebSocket 接続ライブラリの失敗戻り値を確認する。"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Awaitable, Callable
from unittest.mock import Mock

import pytest
from obswsc.data import Event
from structlog.stdlib import BoundLogger

import splat_replay.infrastructure.adapters.obs.websocket_client as websocket_module
from splat_replay.infrastructure.adapters.obs.websocket_client import (
    InputVolumeMeterSample,
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


@pytest.mark.asyncio
async def test_meter_windows_reset_peaks_and_close_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    advance_window = asyncio.Event()
    meter_client_created = asyncio.Event()
    meter_clients: list[_MeterClientStub] = []

    class _MeterClientStub:
        def __init__(self, *, url: str, password: str) -> None:
            self.task: asyncio.Future[None] = (
                asyncio.get_running_loop().create_future()
            )
            self.connected = asyncio.Event()
            self.disconnected = asyncio.Event()
            self.callback: Callable[[Event], Awaitable[None]] | None = None
            meter_clients.append(self)
            meter_client_created.set()

        def reg_event_cb(
            self,
            callback: Callable[[Event], Awaitable[None]],
            event_type: str,
        ) -> None:
            self.callback = callback

        async def connect(self) -> bool:
            self.connected.set()
            return True

        async def subscribe(self, subscriptions: int) -> None:
            return None

        async def disconnect(self) -> None:
            self.disconnected.set()

        async def emit(self, inputs: list[dict[str, object]]) -> None:
            assert self.callback is not None
            await self.callback(
                Event(
                    event_type="InputVolumeMeters",
                    event_intent=0,
                    event_data={"inputs": inputs},
                )
            )

    class _ControlledAsyncio:
        def __getattr__(self, name: str) -> object:
            return getattr(asyncio, name)

        async def wait(
            self,
            futures: set[asyncio.Future[None]],
            *,
            timeout: float | None = None,
        ) -> tuple[set[asyncio.Future[None]], set[asyncio.Future[None]]]:
            if meter_clients and futures == {meter_clients[0].task}:
                await advance_window.wait()
                advance_window.clear()
                return set(), set(futures)
            return await asyncio.wait(futures, timeout=timeout)

    client = OBSWebSocketClient("localhost", 4455, "", Mock(spec=BoundLogger))
    monkeypatch.setattr(websocket_module, "ObsWsClient", _MeterClientStub)
    monkeypatch.setattr(websocket_module, "asyncio", _ControlledAsyncio())
    windows = client.iter_input_volume_meter_windows(window_seconds=1.0)
    first_window_task = asyncio.create_task(anext(windows))
    await asyncio.wait_for(meter_client_created.wait(), timeout=0.5)
    meter_client = meter_clients[0]
    await asyncio.wait_for(meter_client.connected.wait(), timeout=0.5)
    await asyncio.wait_for(
        meter_client.emit(
            [
                {
                    "inputName": "Mic",
                    "inputLevelsMul": [[0.2, 0.9]],
                    "inputLevelsDb": [[-30.0, -6.0]],
                }
            ]
        ),
        timeout=0.5,
    )
    advance_window.set()
    first_window = await asyncio.wait_for(first_window_task, timeout=0.5)

    await asyncio.wait_for(
        meter_client.emit(
            [
                {
                    "inputName": "Mic",
                    "inputLevelsMul": [[0.0002]],
                }
            ]
        ),
        timeout=0.5,
    )
    second_window_task = asyncio.create_task(anext(windows))
    advance_window.set()
    second_window = await asyncio.wait_for(second_window_task, timeout=0.5)
    await asyncio.wait_for(windows.aclose(), timeout=2.0)
    await asyncio.wait_for(client.drain_meter_cleanup_tasks(), timeout=2.0)

    assert first_window["Mic"] == InputVolumeMeterSample(
        event_count=1,
        numeric_mul_samples=1,
        numeric_db_samples=1,
        peak_mul=0.9,
        peak_db=-6.0,
    )
    assert second_window["Mic"] == InputVolumeMeterSample(
        event_count=1,
        numeric_mul_samples=1,
        numeric_db_samples=0,
        peak_mul=0.0002,
        peak_db=None,
    )
    assert meter_client.disconnected.is_set()
    assert client._meter_cleanup_tasks == set()
