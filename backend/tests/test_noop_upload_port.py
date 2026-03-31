"""NoOpUploadPort のテスト。"""

from pathlib import Path
from unittest.mock import MagicMock

from splat_replay.application.interfaces import Caption
from splat_replay.infrastructure.adapters.upload.noop_upload_port import (
    NoOpUploadPort,
)


def test_upload_logs_thumbnail_and_caption_flags() -> None:
    """upload() は外部通信せず、状態を記録して終了する。"""
    logger = MagicMock()
    port = NoOpUploadPort(logger=logger)
    caption = Caption(
        subtitle=Path("C:/tmp/subtitle.srt"),
        caption_name="テスト字幕",
        language="ja",
    )

    port.upload(
        path=Path("C:/tmp/input.mp4"),
        title="テスト動画",
        description="説明",
        privacy_status="public",
        thumb=Path("C:/tmp/thumb.png"),
        caption=caption,
        playlist_id="playlist-123",
    )

    logger.info.assert_called_once_with(
        "E2E no-op upload: upload skipped",
        path=str(Path("C:/tmp/input.mp4")),
        title="テスト動画",
        privacy_status="public",
        has_thumbnail=True,
        has_caption=True,
        playlist_id="playlist-123",
    )
