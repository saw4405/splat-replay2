import queue
import threading
import time
from typing import Optional, Tuple, cast

from splat_replay.application.interfaces import EventPublisher
from splat_replay.domain.models import Frame

EventPayload = Tuple[str, dict[str, object]]
QueueItem = Tuple[str, EventPayload | Frame]


class PublisherWorker:
    """イベントとフレームの publish をバックグラウンドスレッドへオフロードするコンポーネント。"""

    def __init__(
        self,
        event_publisher: EventPublisher,
        queue_maxsize: int = 200,
        idle_sleep: float = 0.01,
    ) -> None:
        self._event_publisher = event_publisher
        self._queue: queue.Queue[QueueItem] = queue.Queue(
            maxsize=queue_maxsize
        )
        self._idle_sleep = idle_sleep
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()

    # Public --------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(
            target=self._loop, name="publish-worker", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if not self._thread:
            return
        self._running.clear()
        # drain remaining queued items (best effort)
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            self._process(kind, payload)
        self._thread.join(timeout=1.0)
        self._thread = None

    def enqueue_event(self, type_: str, payload: dict[str, object]) -> None:
        try:
            self._queue.put_nowait(("event", (type_, payload)))
        except queue.Full:
            pass

    # Internal ------------------------------------------------------
    def _loop(self) -> None:
        while self._running.is_set():
            try:
                try:
                    kind, payload = self._queue.get(timeout=self._idle_sleep)
                except queue.Empty:
                    time.sleep(self._idle_sleep)
                    continue
                self._process(kind, payload)
            except Exception:
                time.sleep(self._idle_sleep)

    def _process(self, kind: str, payload: EventPayload | Frame) -> None:
        if kind == "event":
            try:
                event_type, event_payload = cast(EventPayload, payload)
                self._event_publisher.publish(event_type, event_payload)
            except Exception:
                pass
