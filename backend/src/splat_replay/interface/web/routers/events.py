"""SSE (Server-Sent Events) ルーター。

責務：
- ドメインイベントの配信
- 進捗イベントの配信
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Protocol, cast

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


class EventLike(Protocol):
    """Event object from EventSubscription.poll()."""

    type: str
    payload: dict[str, Any]


def create_events_router(server: WebAPIServer) -> APIRouter:
    """SSEイベントルーターを作成。

    Args:
        server: WebAPIServerインスタンス

    Returns:
        設定済みのAPIRouter
    """
    router = APIRouter(prefix="/api/events", tags=["events"])

    @router.get("/progress")
    async def progress_events() -> EventSourceResponse:
        """進捗イベントをSSE (Server-Sent Events) でストリーム配信。"""

        async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
            sub = server.event_bus.subscribe(
                event_types={
                    "progress.start",
                    "progress.total",
                    "progress.stage",
                    "progress.advance",
                    "progress.finish",
                    "progress.items",
                    "progress.item_stage",
                    "progress.item_finish",
                }
            )
            try:
                while True:
                    events = sub.poll(max_items=10)
                    if events:
                        server.logger.info(
                            "SSE: Polling progress events",
                            count=len(events),
                        )
                    for ev in events:
                        event = cast(EventLike, ev)
                        server.logger.info(
                            "SSE: Sending progress event",
                            event_type=event.type,
                        )
                        yield {
                            "event": "progress_event",
                            "data": json.dumps(event.payload),
                        }
                    if not events:
                        await asyncio.sleep(0.1)
            finally:
                sub.close()

        return EventSourceResponse(event_generator())

    @router.get("/domain-events")
    async def domain_events() -> EventSourceResponse:
        """ドメインイベントをSSE (Server-Sent Events) でストリーム配信。"""

        async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
            sub = server.event_bus.subscribe(event_types=None)
            try:
                while True:
                    events = sub.poll(max_items=10)
                    for ev in events:
                        event = cast(EventLike, ev)
                        if not event.type.startswith("domain."):
                            continue
                        yield {
                            "event": "domain_event",
                            "data": json.dumps(
                                {"type": event.type, "payload": event.payload}
                            ),
                        }
                    if not events:
                        await asyncio.sleep(0.1)
            finally:
                sub.close()

        return EventSourceResponse(event_generator())

    return router


__all__ = ["create_events_router"]
