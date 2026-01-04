"""Infrastructure runtime hosting asyncio loop (moved)."""

from __future__ import annotations

import asyncio
import threading
from typing import Callable, Optional

from splat_replay.infrastructure.messaging import (
    CommandBus,
    EventBus,
    FrameHub,
)


class AppRuntime:
    def __init__(self) -> None:
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self.event_bus = EventBus()
        self.frame_hub = FrameHub()
        self.command_bus = CommandBus()
        self._shutdown = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def runner() -> None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            # command_bus に loop を通知（GUI スレッドからの submit 用）
            try:
                self.command_bus.set_loop(self.loop)
            except Exception:
                pass
            assert self.loop
            self.loop.create_task(self._monitor())
            self.loop.run_forever()
            pending = asyncio.all_tasks(self.loop)
            for t in pending:
                t.cancel()
            try:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            except Exception:
                pass
            self.loop.close()

        self._thread = threading.Thread(
            target=runner, name="AppRuntimeLoop", daemon=True
        )
        self._thread.start()
        while self.loop is None:
            pass

    async def _monitor(self) -> None:
        while not self._shutdown.is_set():
            await asyncio.sleep(0.2)

    def stop(self) -> None:
        self._shutdown.set()
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def call_soon(self, cb: Callable[[], None]) -> None:
        if self.loop:
            self.loop.call_soon_threadsafe(cb)


__all__ = ["AppRuntime"]
