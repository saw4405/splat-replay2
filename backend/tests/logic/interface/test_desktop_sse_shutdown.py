"""常時接続したSSEがデスクトップの正常終了を妨げないことを実TCPで確認する。"""

import threading
import time
import socket
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from unittest.mock import Mock
from typing import cast

import httpx
import uvicorn
from fastapi import FastAPI

from splat_replay.interface.gui.webview_app import _request_backend_shutdown
from splat_replay.interface.web.routers.events import create_events_router
from splat_replay.interface.web.server import WebAPIServer


def test_shutdown_closes_both_sse_streams_before_lifespan_cleanup() -> None:
    shutdown = threading.Event()
    cleaned = threading.Event()
    dependency = Mock()
    dependency.progress_store.read_since.return_value = ([], 0)
    subscription = dependency.event_bus.subscribe.return_value
    subscription.poll.return_value = []

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        cleaned.set()

    app = FastAPI(lifespan=lifespan)
    app.state.desktop_shutdown_event = shutdown
    app.include_router(create_events_router(cast(WebAPIServer, dependency)))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="error", ws="none")
        )
        thread = threading.Thread(
            target=lambda: server.run(sockets=[listener]), daemon=True
        )
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=5
            ) as client:
                with client.stream("GET", "/api/events/progress") as progress:
                    with client.stream(
                        "GET", "/api/events/domain-events"
                    ) as domain:
                        assert (
                            progress.status_code == domain.status_code == 200
                        )
                        shutdown.set()
                        _request_backend_shutdown(shutdown, server)  # type: ignore[arg-type]
                        thread.join(3)
                        assert not thread.is_alive(), (
                            "SSEクライアントを閉じる前に終了する"
                        )
                        assert cleaned.is_set()
                        subscription.close.assert_called_once()
        finally:
            server.should_exit = True
            thread.join(5)
