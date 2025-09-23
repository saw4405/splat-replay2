import queue
import threading
import time
from typing import Any, Optional, Tuple, cast

from splat_replay.application.interfaces import EventPublisher, FramePublisher
from splat_replay.domain.models import Frame

EventPayload = Tuple[str, dict[str, Any]]
QueueItem = Tuple[str, EventPayload | Frame]


class PublisherWorker:
    """イベントとフレームの publish をバックグラウンドスレッドへオフロードするコンポーネント。"""

    def __init__(
        self,
        event_publisher: EventPublisher,
        frame_publisher: Optional[FramePublisher],
        queue_maxsize: int = 200,
        idle_sleep: float = 0.01,
    ) -> None:
        self._event_publisher = event_publisher
        self._frame_publisher = frame_publisher
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

    def enqueue_event(self, type_: str, payload: dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(("event", (type_, payload)))
        except queue.Full:
            pass

    def enqueue_frame(self, frame: Frame) -> None:
        if self._frame_publisher is None:
            return
        try:
            self._queue.put_nowait(("frame", frame))
        except queue.Full:
            pass

    # Internal ------------------------------------------------------
    def _loop(self) -> None:
        while self._running.is_set():
            try:
                try:
                    kind, payload = self._queue.get(timeout=0.1)
                except queue.Empty:
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
        elif kind == "frame" and self._frame_publisher is not None:
            try:
                frame = cast(Frame, payload)
                self._frame_publisher.publish_frame(frame)
            except Exception:
                pass
