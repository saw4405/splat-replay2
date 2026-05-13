import queue
import threading
import time
from typing import Optional

from splat_replay.application.interfaces import CapturePort, FramePublisher
from splat_replay.domain.models import Frame


class FrameCaptureProducer:
    """キャプチャデバイスからフレームを取得し内部キューへ供給するサブコンポーネント。

    - 非同期ループ本体からは thread-safe な queue.Queue 経由で最新フレームを pull する
    - 遅延抑制のためキュー満杯時は最古フレームを破棄
    - GUI へは即時に publish (非同期フローをブロックしない)
    """

    def __init__(
        self,
        capture: CapturePort,
        frame_publisher: Optional[FramePublisher],
        queue_maxsize: int = 1,
        device_retry_sleep: float = 0.1,
        queue_put_timeout: float = 0.001,
    ) -> None:
        self._capture = capture
        self._frame_publisher = frame_publisher
        self._queue: queue.Queue[Frame] = queue.Queue(maxsize=queue_maxsize)
        self._device_retry_sleep = device_retry_sleep
        self._queue_put_timeout = queue_put_timeout
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._generation_lock = threading.Lock()
        self._generation = 0

    # Public API ----------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._drain_queue()
        self._running.set()
        generation = self._next_generation()
        self._thread = threading.Thread(
            target=self._loop,
            args=(generation,),
            name="capture-producer",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if not self._thread:
            return
        self._running.clear()
        self._next_generation()
        self._thread.join(timeout=1.5)
        self._thread = None
        self._drain_queue()

    def get_frame(self, timeout: float) -> Frame | None:
        try:
            return self._queue.get(True, timeout)
        except queue.Empty:
            return None

    # 非ブロッキングで "最新" フレームを取得する。
    # キューに複数たまっている場合は全て捨てて最後の1枚のみ返す。
    def latest(self) -> Frame | None:
        last: Frame | None = None
        while True:
            try:
                item = self._queue.get_nowait()
                last = item
            except queue.Empty:
                break
        return last

    def _drain_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def _next_generation(self) -> int:
        with self._generation_lock:
            self._generation += 1
            return self._generation

    def _is_current_generation(self, generation: int) -> bool:
        with self._generation_lock:
            return generation == self._generation

    # Internal ------------------------------------------------------
    def _loop(self, generation: int) -> None:
        while self._running.is_set() and self._is_current_generation(
            generation
        ):
            try:
                frame = self._capture.capture()
                if (
                    not self._running.is_set()
                    or not self._is_current_generation(generation)
                ):
                    break
                if frame is None:
                    time.sleep(self._device_retry_sleep)
                    continue

                # publish latest to GUI
                if self._frame_publisher is not None:
                    try:
                        self._frame_publisher.publish_frame(frame)
                    except Exception:
                        pass

                # enqueue (replace oldest if full)
                try:
                    self._queue.put(frame, timeout=self._queue_put_timeout)
                except queue.Full:
                    try:
                        _ = self._queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._queue.put_nowait(frame)
                    except queue.Full:
                        pass
            except Exception:
                time.sleep(self._device_retry_sleep)
