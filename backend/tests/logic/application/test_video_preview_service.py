"""ブラウザー再生形式の選択を確認する。"""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest

from splat_replay.application.interfaces import VideoPreviewPort
from splat_replay.application.services.playback.video_preview import (
    VideoPreviewService,
)


@pytest.mark.asyncio
async def test_mp4_is_reused_and_mkv_is_prepared(tmp_path: Path) -> None:
    """MP4 はそのまま返し、MKV だけを変換ポートへ渡す。"""
    mp4 = tmp_path / "source.mp4"
    mkv = tmp_path / "source.mkv"
    preview = tmp_path / "preview.mp4"
    port = AsyncMock()
    port.create_mp4_preview.return_value = preview
    service = VideoPreviewService(cast(VideoPreviewPort, port))

    assert await service.prepare(mp4) == mp4
    assert await service.prepare(mkv) == preview
    port.create_mp4_preview.assert_awaited_once_with(mkv)
