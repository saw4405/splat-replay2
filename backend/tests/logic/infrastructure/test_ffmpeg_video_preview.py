"""一時 MP4 の保全、同時生成、失敗時 cleanup を確認する。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import VideoPreviewError
from splat_replay.infrastructure.adapters.video.ffmpeg_video_preview import (
    FFmpegVideoPreviewAdapter,
)


class _FakeFFmpegPreview(FFmpegVideoPreviewAdapter):
    def __init__(self) -> None:
        super().__init__(cast(BoundLogger, MagicMock(spec=BoundLogger)))
        self.commands: list[list[str]] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.fail = False
        self.block = False
        self.pixel_format = "yuv420p"

    async def _probe(self, ffprobe: str, source: Path) -> list[dict[str, str]]:
        return [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": self.pixel_format,
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ]

    async def _run(self, executable: str, command: list[str]) -> str:
        self.commands.append(command)
        output = Path(command[-1])
        output.write_bytes(b"partial")
        self.started.set()
        if self.block:
            await self.release.wait()
        if self.fail:
            raise VideoPreviewError("FFmpeg failed")
        output.write_bytes(b"complete MP4")
        return ""


@pytest.fixture(autouse=True)
def fake_ffmpeg_binaries(monkeypatch: pytest.MonkeyPatch) -> None:
    """外部 FFmpeg を起動せず、adapter の境界を検証する。"""
    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.video.ffmpeg_video_preview.shutil.which",
        lambda name: f"/fake/{name}",
    )


@pytest.mark.asyncio
async def test_concurrent_requests_share_complete_preview_and_preserve_source(
    tmp_path: Path,
) -> None:
    """同じ MKV の要求は生成を共有し、原本を変更しない。"""
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"original MKV")
    original = source.read_bytes()
    adapter = _FakeFFmpegPreview()
    adapter.block = True
    try:
        first = asyncio.create_task(adapter.create_mp4_preview(source))
        second = asyncio.create_task(adapter.create_mp4_preview(source))
        await adapter.started.wait()
        assert len(adapter.commands) == 1
        adapter.release.set()
        first_path, second_path = await asyncio.gather(first, second)

        assert first_path == second_path
        assert first_path.read_bytes() == b"complete MP4"
        assert source.read_bytes() == original
        assert ["-c:v", "copy"] == adapter.commands[0][
            adapter.commands[0].index("-c:v") : adapter.commands[0].index(
                "-c:v"
            )
            + 2
        ]
        assert ["-c:a", "copy"] == adapter.commands[0][
            adapter.commands[0].index("-c:a") : adapter.commands[0].index(
                "-c:a"
            )
            + 2
        ]

        assert await adapter.create_mp4_preview(source) == first_path
        assert len(adapter.commands) == 1
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_source_update_uses_new_preview(tmp_path: Path) -> None:
    """入力更新後は前の一時 MP4 を再利用しない。"""
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"original")
    adapter = _FakeFFmpegPreview()
    adapter.release.set()
    try:
        old_preview = await adapter.create_mp4_preview(source)
        source.write_bytes(b"updated source with a different size")
        new_preview = await adapter.create_mp4_preview(source)

        assert new_preview != old_preview
        assert len(adapter.commands) == 2
        assert source.read_bytes() == b"updated source with a different size"
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_unsupported_h264_pixel_format_is_transcoded(
    tmp_path: Path,
) -> None:
    """H.264 でも WebView 非対応の画素形式をコピーしない。"""
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"source")
    adapter = _FakeFFmpegPreview()
    adapter.pixel_format = "yuv444p"
    try:
        await adapter.create_mp4_preview(source)
        command = adapter.commands[0]
        assert command[command.index("-c:v") : command.index("-c:v") + 2] == [
            "-c:v",
            "libx264",
        ]
        assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_failed_or_cancelled_generation_removes_partial_output(
    tmp_path: Path,
) -> None:
    """失敗・最後の要求のキャンセルでは未完成 MP4 を残さない。"""
    source = tmp_path / "recording.mkv"
    source.write_bytes(b"original")
    adapter = _FakeFFmpegPreview()
    cache_dir = adapter._cache_dir
    try:
        adapter.fail = True
        with pytest.raises(VideoPreviewError, match="FFmpeg failed"):
            await adapter.create_mp4_preview(source)
        assert list(cache_dir.iterdir()) == []

        adapter.fail = False
        adapter.block = True
        source.write_bytes(b"updated")
        adapter.started = asyncio.Event()
        request = asyncio.create_task(adapter.create_mp4_preview(source))
        await adapter.started.wait()
        generation = next(iter(adapter._inflight.values()))
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        await asyncio.gather(generation, return_exceptions=True)
        assert list(cache_dir.iterdir()) == []
    finally:
        await adapter.close()
