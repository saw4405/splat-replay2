"""AutoUploader の実行制御を検証する。

分類: logic
"""

from typing import cast
from unittest.mock import MagicMock

import pytest

from splat_replay.application.interfaces import (
    ConfigPort,
    FileSystemPort,
    LoggerPort,
    UploadPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.application.services.common.progress import ProgressReporter
from splat_replay.application.services.upload.auto_uploader import AutoUploader


@pytest.mark.asyncio
async def test_execute_resets_previous_cancellation_request() -> None:
    repo = MagicMock()
    repo.list_edited.return_value = []
    progress = MagicMock()
    uploader = AutoUploader(
        uploader=cast(UploadPort, MagicMock()),
        video_editor=cast(VideoEditorPort, MagicMock()),
        config=cast(ConfigPort, MagicMock()),
        repo=cast(VideoAssetRepositoryPort, repo),
        logger=cast(LoggerPort, MagicMock()),
        file_system=cast(FileSystemPort, MagicMock()),
        progress=cast(ProgressReporter, progress),
    )
    uploader._cancelled = True

    await uploader.execute()

    assert uploader._cancelled is False
    progress.finish.assert_called_once_with(
        "auto_upload", True, "自動アップロードを完了しました"
    )
