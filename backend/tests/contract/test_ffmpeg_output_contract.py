"""FFmpegProcessor が実動画を生成し、連結順とメタデータを保つ契約。"""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
import shutil
import subprocess
import threading
from typing import Callable
from unittest.mock import MagicMock

from PIL import Image
import pytest

from splat_replay.infrastructure.adapters.video.ffmpeg_processor import (
    FFmpegProcessor,
)

pytestmark = pytest.mark.contract


def _require_binary(name: str) -> str:
    binary = shutil.which(name)
    if binary is None:
        pytest.skip(f"release contract requires {name} on PATH")
    assert binary is not None
    return binary


def _make_color_clip(ffmpeg: str, path: Path, color: str) -> None:
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=32x32:r=2:d=1",
            "-frames:v",
            "2",
            "-c:v",
            "ffv1",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.mark.asyncio
async def test_merge_and_metadata_produce_probeable_video_with_clip_order(
    tmp_path: Path,
) -> None:
    ffmpeg = _require_binary("ffmpeg")
    ffprobe = _require_binary("ffprobe")
    first = tmp_path / "first.mkv"
    second = tmp_path / "second.mkv"
    output = tmp_path / "merged.mkv"
    _make_color_clip(ffmpeg, first, "red")
    _make_color_clip(ffmpeg, second, "blue")
    processor = FFmpegProcessor(MagicMock())

    await processor.merge([first, second], output)
    await processor.embed_metadata(output, {"title": "contract output"})

    assert output.is_file()
    assert (await processor.get_metadata(output))["title"] == "contract output"
    duration = await processor.get_video_length(output)
    # 2 fps の合成入力なので、duration は連結境界の最大1フレーム分を許容する。
    assert duration is not None and abs(duration - 2.0) < 0.5

    probe = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,nb_read_frames",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    streams = json.loads(probe.stdout)["streams"]
    assert streams == [{"codec_name": "ffv1", "nb_read_frames": "4"}]

    red_png = await processor.extract_frame(output, 0)
    blue_png = await processor.extract_frame(output, 1)
    assert red_png and blue_png
    red = Image.open(io.BytesIO(red_png)).convert("RGB").tobytes()
    blue = Image.open(io.BytesIO(blue_png)).convert("RGB").tobytes()
    pixel_offset = (16 * 32 + 16) * 3
    assert red[pixel_offset] > red[pixel_offset + 2]
    assert blue[pixel_offset + 2] > blue[pixel_offset]


@pytest.mark.asyncio
async def test_real_ffmpeg_cancel_waits_for_child_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ffmpeg = _require_binary("ffmpeg")
    processor = FFmpegProcessor(MagicMock())
    cancel_requested = threading.Event()
    progress_seen = threading.Event()
    children: list[subprocess.Popen[bytes]] = []
    start_cancel_watcher = processor._start_cancel_watcher

    def track_child(
        process: subprocess.Popen[bytes],
        cancel_check: Callable[[], bool] | None,
    ) -> tuple[threading.Event, threading.Thread] | None:
        children.append(process)
        return start_cancel_watcher(process, cancel_check)

    monkeypatch.setattr(processor, "_start_cancel_watcher", track_child)

    def on_progress(percent: float, message: str | None) -> None:
        _ = percent, message
        progress_seen.set()
        cancel_requested.set()

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "info",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "color=c=green:s=64x64:r=30",
        "-t",
        "60",
        "-f",
        "null",
        "-",
    ]
    process_task = asyncio.create_task(
        processor._run_with_progress(
            command,
            10.0,
            on_progress,
            cancel_check=cancel_requested.is_set,
        )
    )
    try:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(process_task), timeout=8)
        assert progress_seen.is_set()
        assert len(children) == 1
        assert children[0].poll() is not None
        assert children[0].returncode is not None
    finally:
        cancel_requested.set()
        for child in children:
            if child.poll() is None:
                processor._terminate_process(child)
        if not process_task.done():
            try:
                await asyncio.wait_for(process_task, timeout=5)
            except asyncio.CancelledError:
                pass
