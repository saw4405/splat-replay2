"""AutoUploader の実行制御を検証する。

分類: logic
"""

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

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


@pytest.mark.asyncio
async def test_execute_keeps_edited_video_when_upload_fails() -> None:
    video = Path("edited/failed.mkv")
    repo = MagicMock()
    repo.list_edited.return_value = [video]
    repo.get_edited_metadata.return_value = {}
    repo.get_edited_thumbnail.return_value = None
    repo.get_edited_subtitle.return_value = None
    upload_port = MagicMock()
    upload_port.upload.side_effect = RuntimeError("upload failed")
    video_editor = MagicMock()
    video_editor.get_metadata = AsyncMock(return_value={"title": "failed"})
    uploader = AutoUploader(
        uploader=cast(UploadPort, upload_port),
        video_editor=cast(VideoEditorPort, video_editor),
        config=cast(ConfigPort, MagicMock()),
        repo=cast(VideoAssetRepositoryPort, repo),
        logger=cast(LoggerPort, MagicMock()),
        file_system=cast(FileSystemPort, MagicMock()),
        progress=cast(ProgressReporter, MagicMock()),
    )

    with pytest.raises(RuntimeError, match="upload failed"):
        await uploader.execute()

    repo.delete_edited.assert_not_called()


@pytest.mark.asyncio
async def test_execute_deletes_edited_video_after_upload_succeeds() -> None:
    video = Path("edited/succeeded.mkv")
    repo = MagicMock()
    repo.list_edited.return_value = [video]
    repo.get_edited_metadata.return_value = {}
    repo.get_edited_thumbnail.return_value = None
    repo.get_edited_subtitle.return_value = None
    repo.delete_edited.return_value = True
    video_editor = MagicMock()
    video_editor.get_metadata = AsyncMock(return_value={"title": "succeeded"})
    uploader = AutoUploader(
        uploader=cast(UploadPort, MagicMock()),
        video_editor=cast(VideoEditorPort, video_editor),
        config=cast(ConfigPort, MagicMock()),
        repo=cast(VideoAssetRepositoryPort, repo),
        logger=cast(LoggerPort, MagicMock()),
        file_system=cast(FileSystemPort, MagicMock()),
        progress=cast(ProgressReporter, MagicMock()),
    )

    await uploader.execute()

    repo.delete_edited.assert_called_once_with(video)
