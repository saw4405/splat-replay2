from __future__ import annotations

from typing import Awaitable, Callable

from .data import Event, Request, Response1, Response2

Response = Response1 | Response2

class ObsWsClient:
    task: Awaitable[object] | None

    def __init__(self, url: str, password: str | None = ...) -> None: ...
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def request(self, request: Request) -> Response: ...
    def reg_event_cb(
        self, callback: Callable[[Event], Awaitable[None]], event_type: str
    ) -> None: ...
