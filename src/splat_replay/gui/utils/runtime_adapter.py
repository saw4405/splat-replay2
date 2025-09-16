"""GUI Runtime Adapter bridging abstract runtime ports <-> Tk GUI (push model)."""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional

import ttkbootstrap as ttk

from splat_replay.application.interfaces import (
    CommandDispatcher,
    EventSubscriber,
    FrameSource,
)
from splat_replay.domain.models import Frame
from splat_replay.infrastructure.runtime.events import Event


class GuiRuntimeAdapter:
    def __init__(
        self,
        dispatcher: CommandDispatcher,
        subscriber: EventSubscriber,
        frame_source: FrameSource,
        tk_root: ttk.Window,
    ) -> None:
        self._dispatcher = dispatcher
        self._subscriber = subscriber
        self._frame_source = frame_source
        self.tk = tk_root

        self._event_queue: queue.SimpleQueue[Event] = queue.SimpleQueue()
        self._event_handlers: list[Callable[[Event], None]] = []
        self._frame_handler: Optional[Callable[[Frame], None]] = None
        self._pump_scheduled = False
        self._closed = False
        # subscriptions
        self._event_sub = self._subscriber.subscribe(event_types=None)
        # start background poll thread (lightweight)
        self._poll_thread = threading.Thread(
            target=self._poll_loop, name="GuiEventPoll", daemon=True
        )
        self._poll_thread.start()
        # register frame listener
        self._frame_source.add_listener(self._on_frame)

    # -------- public API -------------------------------------------------
    def add_event_handler(self, handler: Callable[[Event], None]) -> None:
        self._event_handlers.append(handler)

    def add_frame_handler(self, handler: Callable[[Frame], None]) -> None:
        self._frame_handler = handler

    def send_command(self, name: str, **payload):  # fire & forget
        return self._dispatcher.submit(name, **payload)

    def call_soon(self, func: Callable[[], None]) -> None:
        """Schedule a callable on the Tk GUI thread ASAP.

        Falls back to direct call if scheduling fails (e.g., during teardown).
        """
        try:
            self.tk.after(0, func)
        except Exception:
            try:
                func()
            except Exception:
                pass

    # -------- internal ---------------------------------------------------
    def _poll_loop(self) -> None:
        while not self._closed:
            events = self._event_sub.poll(max_items=50)
            if events:
                for ev in list(events):
                    self._event_queue.put(ev)
                self._schedule_pump()
            else:
                time.sleep(0.05)

    def _schedule_pump(self) -> None:
        if self._pump_scheduled or self._closed:
            return
        self._pump_scheduled = True
        self.tk.after(0, self._drain_events)

    def _drain_events(self) -> None:
        self._pump_scheduled = False
        while True:
            try:
                ev = self._event_queue.get_nowait()
            except Exception:
                break
            for h in list(self._event_handlers):
                try:
                    h(ev)
                except Exception:
                    pass

    def _on_frame(self, pkt: Frame) -> None:
        if self._frame_handler is None:
            return

        frame_handler = self._frame_handler

        def safe_call_frame(pkt: Frame) -> None:
            try:
                frame_handler(pkt)
            except Exception:
                pass

        # marshal to GUI thread
        self.tk.after(0, lambda p=pkt: safe_call_frame(p))

    def close(self) -> None:
        self._closed = True
        try:
            self._frame_source.remove_listener(self._on_frame)
        except Exception:
            pass
        try:
            self._event_sub.close()
        except Exception:
            pass


__all__ = ["GuiRuntimeAdapter"]
