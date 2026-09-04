from __future__ import annotations

import asyncio
from pathlib import Path
from subprocess import CompletedProcess
from typing import Sequence
from unittest.mock import MagicMock

import pytest

from splat_replay.infrastructure.adapters.video.ffmpeg_processor import (
    FFmpegProcessor,
)


class _FramePreviewProcessor(FFmpegProcessor):
    def __init__(self) -> None:
        super().__init__(MagicMock())
        self.commands: list[list[str]] = []
        self.active_runs = 0
        self.max_active_runs = 0

    async def _run_binary(
        self,
        command: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout: float | None = None,
        **kwargs: object,
    ) -> CompletedProcess[bytes]:
        _ = input_bytes, timeout, kwargs
        self.commands.append(list(command))
        self.active_runs += 1
        self.max_active_runs = max(self.max_active_runs, self.active_runs)
        try:
            await asyncio.sleep(0.01)
            return CompletedProcess(
                args=list(command),
                returncode=0,
                stdout=b"png-bytes",
                stderr=b"",
            )
        finally:
            self.active_runs -= 1


@pytest.mark.asyncio
async def test_extract_frame_runs_ffmpeg_for_each_request_without_persistent_cache(
    tmp_path: Path,
) -> None:
    processor = _FramePreviewProcessor()
    video = tmp_path / "videos" / "recorded" / "sample.mkv"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")

    first = await processor.extract_frame(video, 60, max_width=960)
    second = await processor.extract_frame(video, 60, max_width=960)

    assert first == b"png-bytes"
    assert second == b"png-bytes"
    assert len(processor.commands) == 2
    assert "scale=960:-2" in processor.commands[0]
    assert not (tmp_path / "videos" / ".progress_frames").exists()


@pytest.mark.asyncio
async def test_extract_frame_returns_none_after_source_video_is_removed(
    tmp_path: Path,
) -> None:
    processor = _FramePreviewProcessor()
    video = tmp_path / "videos" / "recorded" / "sample.mkv"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")

    first = await processor.extract_frame(video, 60, max_width=960)
    video.unlink()
    second = await processor.extract_frame(video, 60, max_width=960)

    assert first == b"png-bytes"
    assert second is None
    assert len(processor.commands) == 1
    assert not (tmp_path / "videos" / ".progress_frames").exists()


@pytest.mark.asyncio
async def test_extract_frame_serializes_preview_requests(
    tmp_path: Path,
) -> None:
    processor = _FramePreviewProcessor()
    video = tmp_path / "videos" / "recorded" / "sample.mkv"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")

    results = await asyncio.gather(
        processor.extract_frame(video, 0, max_width=960),
        processor.extract_frame(video, 60, max_width=960),
        processor.extract_frame(video, 120, max_width=960),
    )

    assert results == [b"png-bytes"] * 3
    assert processor.max_active_runs == 1
