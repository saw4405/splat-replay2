"""持込動画を逐次デコードして解析用フレームを取り出す。"""

from __future__ import annotations

import asyncio
import contextlib
import math
import threading
from collections.abc import AsyncIterator
from pathlib import Path

import cv2

from splat_replay.application.interfaces.imported_video import (
    ImportedVideoFrameReaderPort,
)
from splat_replay.domain.models import Frame, as_frame


class OpenCVImportedVideoFrameReader(ImportedVideoFrameReaderPort):
    """OpenCVを使い、一定間隔でフレームを返す。全フレームは保持しない。"""

    def frames(
        self, path: Path, sample_interval_seconds: float
    ) -> AsyncIterator[tuple[float, Frame]]:
        if (
            not math.isfinite(sample_interval_seconds)
            or sample_interval_seconds <= 0
        ):
            raise ValueError("フレームを確認する間隔を正しく指定してください")

        async def iterate() -> AsyncIterator[tuple[float, Frame]]:
            def open_capture() -> cv2.VideoCapture:
                return cv2.VideoCapture(str(path))

            capture = await asyncio.to_thread(open_capture)
            if not capture.isOpened():
                await asyncio.to_thread(capture.release)
                raise ValueError(
                    "動画を読み込めません。ファイル形式を確認してください。"
                )
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_number = 0
            next_sample = 0.0
            stop = threading.Event()

            def read_sample() -> tuple[float, Frame] | None:
                nonlocal frame_number
                while not stop.is_set():
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        return None
                    frame_number += 1
                    position_msec = float(
                        capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0
                    )
                    if position_msec > 0:
                        seconds = position_msec / 1000.0
                    elif fps > 0:
                        seconds = (frame_number - 1) / fps
                    elif frame_number == 1:
                        seconds = 0.0
                    else:
                        raise ValueError(
                            "動画の時刻情報を読み取れませんでした"
                        )
                    if seconds + 0.001 >= next_sample:
                        return seconds, as_frame(frame)

            try:
                while True:
                    read_task = asyncio.create_task(
                        asyncio.to_thread(read_sample)
                    )
                    try:
                        sample = await asyncio.shield(read_task)
                    except asyncio.CancelledError:
                        stop.set()
                        with contextlib.suppress(asyncio.CancelledError):
                            await asyncio.shield(read_task)
                        raise
                    if sample is None:
                        return
                    seconds, frame = sample
                    next_sample = seconds + sample_interval_seconds
                    yield seconds, frame
            finally:
                stop.set()
                await asyncio.to_thread(capture.release)

        return iterate()
