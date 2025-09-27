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
from splat_replay.shared.logger import get_logger


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
        self._stop_event = threading.Event()
        self._logger = get_logger()
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

    def call_soon(
        self,
        func: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> None:
        def invoke() -> None:
            try:
                func(*args, **kwargs)
            except Exception:
                pass

        try:
            self.tk.after(0, invoke)
        except Exception:
            invoke()

    # -------- internal ---------------------------------------------------
    def _poll_loop(self) -> None:
        # Poll in a loop but wake up promptly on close via _stop_event.
        while not self._stop_event.is_set():
            try:
                events = self._event_sub.poll(max_items=50)
            except Exception as e:
                # Log and back off briefly to avoid tight loop on persistent errors
                try:
                    self._logger.error(
                        "Event subscriber poll error", error=str(e)
                    )
                except Exception:
                    pass
                time.sleep(0.1)
                continue

            if events:
                for ev in list(events):
                    try:
                        self._event_queue.put(ev)
                    except Exception:
                        # queue.SimpleQueue.put shouldn't fail, but guard anyway
                        pass
                self._schedule_pump()
            else:
                # wait with timeout so we can react to stop_event faster
                self._stop_event.wait(0.05)

    def _schedule_pump(self) -> None:
        if self._pump_scheduled or self._stop_event.is_set():
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
        try:
            self._stop_event.set()
        except Exception:
            pass
        try:
            self._frame_source.remove_listener(self._on_frame)
        except Exception:
            pass
        try:
            self._event_sub.close()
        except Exception:
            pass
        try:
            if self._poll_thread.is_alive():
                # give a short timeout to avoid hanging shutdown
                self._poll_thread.join(timeout=0.5)
        except Exception:
            pass
        try:
            self._logger.info("GuiRuntimeAdapter closed")
        except Exception:
            pass


__all__ = ["GuiRuntimeAdapter"]
