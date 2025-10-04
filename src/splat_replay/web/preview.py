"""プレビュー映像配信のユーティリティ。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import cv2
from structlog.stdlib import BoundLogger

from splat_replay.domain.models.aliases import Frame
from splat_replay.infrastructure.runtime.frames import FrameHub


async def mjpeg_stream(
    hub: FrameHub,
    *,
    boundary: str = "frame",
    logger: BoundLogger | None = None,
) -> AsyncIterator[bytes]:
    """フレームを MJPEG ストリームとして逐次エンコードする。"""

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Frame] = asyncio.Queue(maxsize=1)
    stopped = False

    def _enqueue(frame: Frame) -> None:
        if stopped:
            return

        frame_copy = frame.copy()

        def _push() -> None:
            if stopped:
                return
            try:
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(frame_copy)
            except Exception:
                pass

        try:
            loop.call_soon_threadsafe(_push)
        except RuntimeError:
            # イベントループ終了時は無視
            pass

    hub.add_listener(_enqueue)

    try:
        while True:
            try:
                frame_item = await queue.get()
            except asyncio.CancelledError:
                break

            ok, buffer = cv2.imencode(".jpg", frame_item)
            if not ok:
                if logger is not None:
                    logger.warning(
                        "プレビューの JPEG エンコードに失敗しました。"
                    )
                continue

            data = buffer.tobytes()
            header = (
                f"--{boundary}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(data)}\r\n\r\n"
            ).encode("ascii")
            yield header + data + b"\r\n"
    finally:
        stopped = True
        hub.remove_listener(_enqueue)


__all__ = ["mjpeg_stream"]
