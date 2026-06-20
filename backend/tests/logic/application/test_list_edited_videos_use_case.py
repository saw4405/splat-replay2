"""ListEditedVideosUseCase のテスト。"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from splat_replay.application.interfaces import ConfigPort, FileSystemPort
from splat_replay.application.services.editing import ThumbnailGenerator
from splat_replay.application.use_cases.assets.list_edited_videos import (
    ListEditedVideosUseCase,
)
from splat_replay.domain.config.video_edit import VideoEditSettings
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
    VideoAsset,
)


class _DummyConfig:
    def get_video_edit_settings(self) -> VideoEditSettings:
        return VideoEditSettings(
            title_template="{BATTLE} / {RULE} / {STAGES}",
            description_template="{WIN}勝{LOSE}敗\n{CHAPTERS}",
        )


class _DummyThumbnailGenerator:
    def __init__(self, thumbnail_path: Path) -> None:
        self.thumbnail_path = thumbnail_path
        self.created_assets: list[VideoAsset] | None = None

    def create(self, assets: list[VideoAsset]) -> Path:
        self.created_assets = assets
        self.thumbnail_path.write_bytes(b"pending-thumbnail")
        return self.thumbnail_path


class _DummyFileSystem:
    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()

    def unlink(self, path: Path, *, missing_ok: bool = True) -> None:
        path.unlink(missing_ok=missing_ok)


def _metadata(
    started_at: dt.datetime, judgement: Judgement
) -> RecordingMetadata:
    return RecordingMetadata(
        game_mode=GameMode.BATTLE,
        started_at=started_at,
        judgement=judgement,
        result=BattleResult(
            match=Match.X,
            rule=Rule.SPLAT_ZONES,
            stage=Stage.MUSEUM_D_ALFONSINO,
            kill=8,
            death=3,
            special=2,
        ),
    )


@pytest.mark.asyncio
async def test_execute_returns_pending_edited_group_for_recorded_timeslot(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "videos"
    recorded_dir = base_dir / "recorded"
    edited_dir = base_dir / "edited"
    recorded_dir.mkdir(parents=True)
    edited_dir.mkdir(parents=True)
    first_video = recorded_dir / "first.mp4"
    second_video = recorded_dir / "second.mp4"
    first_video.write_bytes(b"first")
    second_video.write_bytes(b"second")
    first_thumbnail = first_video.with_suffix(".png")
    first_thumbnail.write_bytes(b"png")

    repository = MagicMock()
    pending_filename = "20260314_11_Xマッチ_ガチエリア.mp4"
    pending_target = edited_dir / pending_filename
    generated_thumbnail = tmp_path / "generated-thumbnail.png"
    repository.list_edited.return_value = []
    repository.get_edited_dir.return_value = edited_dir
    repository.list_recordings.return_value = [
        VideoAsset(
            video=first_video,
            thumbnail=first_thumbnail,
            metadata=_metadata(
                dt.datetime(2026, 3, 14, 12, 30), Judgement.WIN
            ),
        ),
        VideoAsset(
            video=second_video,
            metadata=_metadata(
                dt.datetime(2026, 3, 14, 12, 45), Judgement.LOSE
            ),
        ),
    ]
    repository.has_thumbnail.side_effect = lambda path: path == first_video
    repository.has_subtitle.return_value = False
    repository.get_file_stats.return_value = type(
        "FileStats",
        (),
        {"size_bytes": 1234, "updated_at": 1773487800.0},
    )()

    video_editor = AsyncMock()
    video_editor.get_video_length.return_value = 180.0

    use_case = ListEditedVideosUseCase(
        repository=repository,
        logger=MagicMock(),
        base_dir=base_dir,
        video_editor=video_editor,
        config=cast(ConfigPort, _DummyConfig()),
        thumbnail_generator=cast(
            ThumbnailGenerator,
            _DummyThumbnailGenerator(generated_thumbnail),
        ),
        file_system=cast(FileSystemPort, _DummyFileSystem()),
    )

    result = await use_case.execute()

    assert len(result) == 1
    pending = result[0]
    assert pending.source == "pending"
    assert pending.playable is False
    assert pending.recorded_video_ids == (
        "recorded/first.mp4",
        "recorded/second.mp4",
    )
    assert pending.thumbnail_source == "edited"
    assert pending.thumbnail_filename == pending_filename
    assert pending.filename == pending_filename
    assert pending.has_thumbnail is True
    repository.save_edited_thumbnail.assert_called_once_with(
        pending_target,
        b"pending-thumbnail",
    )
    assert not generated_thumbnail.exists()
    assert pending.title is not None
    assert "Xマッチ" in pending.title
    assert pending.description is not None
    assert "1勝1敗" in pending.description
