from __future__ import annotations

from collections.abc import Iterator
import datetime
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from splat_replay.application.services.editing.auto_editor import AutoEditor
from splat_replay.application.services.editing.editing_state import (
    EditingState,
)


class _FakeThumbnailGenerator:
    def __init__(self, thumbnail: Path) -> None:
        self.thumbnail = thumbnail

    def create(self, assets: list[Any]) -> Path:
        _ = assets
        self.thumbnail.write_bytes(b"thumbnail-data")
        return self.thumbnail


class _FakeFileSystem:
    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()

    def unlink(self, path: Path, *, missing_ok: bool = False) -> None:
        path.unlink(missing_ok=missing_ok)


class _FakeVideoEditor:
    def __init__(self) -> None:
        self.combined_calls: list[tuple[Path, dict[str, str], bytes]] = []
        self.metadata_only_calls: list[tuple[Path, dict[str, str]]] = []

    async def embed_metadata_and_thumbnail(
        self,
        path: Path,
        metadata: dict[str, str],
        thumbnail: bytes,
        *,
        on_progress,
    ) -> None:
        self.combined_calls.append((path, metadata, thumbnail))
        on_progress(33.0, "埋め込み中")

    async def embed_metadata(
        self, path: Path, metadata: dict[str, str]
    ) -> None:
        self.metadata_only_calls.append((path, metadata))


class _FakeRepo:
    def __init__(self, edited_dir: Path) -> None:
        self.edited_dir = edited_dir
        self.metadata_calls: list[tuple[Path, dict[str, str]]] = []
        self.thumbnail_calls: list[tuple[Path, bytes]] = []

    def get_edited_dir(self) -> Path:
        return self.edited_dir

    def save_edited_metadata_dict(
        self, target: Path, metadata: dict[str, str]
    ) -> None:
        self.metadata_calls.append((target, metadata))

    def save_edited_thumbnail(self, target: Path, data: bytes) -> bool:
        self.thumbnail_calls.append((target, data))
        return True


class _FakeProgress:
    def __init__(self) -> None:
        self.item_stage_calls: list[dict[str, object]] = []
        self.start_task_calls: list[dict[str, object]] = []
        self.advance_calls: list[str] = []
        self.finish_calls: list[dict[str, object]] = []

    def start_task(
        self,
        task_id: str,
        task_name: str,
        total: int | None,
        *,
        items: list[str] | None = None,
        clips: list[dict[str, object]] | None = None,
    ) -> None:
        self.start_task_calls.append(
            {
                "task_id": task_id,
                "task_name": task_name,
                "total": total,
                "items": items,
                "clips": clips,
            }
        )

    def item_stage(
        self,
        task_id: str,
        item_index: int,
        stage_key: str,
        stage_label: str,
        *,
        message: str | None = None,
        progress_percent: float | None = None,
    ) -> None:
        self.item_stage_calls.append(
            {
                "task_id": task_id,
                "item_index": item_index,
                "stage_key": stage_key,
                "stage_label": stage_label,
                "message": message,
                "progress_percent": progress_percent,
            }
        )

    def advance(self, task_id: str) -> None:
        self.advance_calls.append(task_id)

    def finish(
        self, task_id: str, success: bool = True, message: str | None = None
    ) -> None:
        self.finish_calls.append(
            {"task_id": task_id, "success": success, "message": message}
        )


@pytest.mark.asyncio
async def test_save_thumbnail_embeds_metadata_and_thumbnail_once_with_progress(
    tmp_path: Path,
) -> None:
    target = tmp_path / "edited.mkv"
    thumbnail = tmp_path / "source.thumb.png"
    metadata = {"title": "title", "description": "description"}
    editor = AutoEditor.__new__(AutoEditor)
    video_editor = _FakeVideoEditor()
    repo = _FakeRepo(tmp_path / "edited")
    progress = _FakeProgress()
    editor.thumbnail_generator = _FakeThumbnailGenerator(thumbnail)
    editor._file_system = _FakeFileSystem()
    editor.video_editor = video_editor
    editor.repo = repo
    editor.progress = progress

    await editor._save_thumbnail(target, [], 2, metadata)

    assert video_editor.combined_calls == [
        (target, metadata, b"thumbnail-data")
    ]
    assert video_editor.metadata_only_calls == []
    assert repo.metadata_calls == [(target, metadata)]
    assert repo.thumbnail_calls == [
        (tmp_path / "edited" / target.name, b"thumbnail-data")
    ]
    assert progress.item_stage_calls == [
        {
            "task_id": "auto_edit",
            "item_index": 2,
            "stage_key": "thumbnail",
            "stage_label": "サムネイル編集",
            "message": None,
            "progress_percent": 0.0,
        },
        {
            "task_id": "auto_edit",
            "item_index": 2,
            "stage_key": "thumbnail",
            "stage_label": "サムネイル編集",
            "message": "埋め込み中",
            "progress_percent": 33.0,
        },
    ]
    assert not thumbnail.exists()


@pytest.mark.asyncio
async def test_execute_saves_group_without_frame_preview_dependency(
    tmp_path: Path,
) -> None:
    generated_title = "【ガチヤグラ】海女美術大学の軌跡"
    source_video = tmp_path / "source.mkv"
    edited_video = tmp_path / "edited.mkv"
    source_video.write_bytes(b"source")

    asset = SimpleNamespace(
        video=source_video,
        metadata=SimpleNamespace(
            judgement=SimpleNamespace(value="WIN"),
            result=SimpleNamespace(
                stage=SimpleNamespace(value="海女美術大学"),
                kill=5,
                death=2,
                special=3,
                gold_medals=1,
                silver_medals=2,
            ),
            rate=None,
        ),
    )

    class _Logger:
        def info(self, *args: object, **kwargs: object) -> None:
            _ = args, kwargs

        def error(self, *args: object, **kwargs: object) -> None:
            _ = args, kwargs

    class _Config:
        def get_video_edit_settings(self) -> object:
            return object()

    deleted_videos: list[Path] = []

    class _Repo:
        def list_recordings(self) -> list[object]:
            return [asset]

        def save_edited(self, target: Path) -> Path:
            return target

        def delete_recording(self, video: Path) -> None:
            deleted_videos.append(video)

    class _Grouping:
        def group_by_timeslot(
            self, assets: list[object]
        ) -> dict[tuple[object, ...], list[object]]:
            return {
                (
                    datetime.date(2026, 6, 27),
                    datetime.time(0, 0),
                    "Xマッチ",
                    "ガチヤグラ",
                ): assets
            }

    class _VideoEditor:
        async def get_video_length(self, video: Path) -> float:
            _ = video
            return 180.0

    progress = _FakeProgress()
    editor = AutoEditor.__new__(AutoEditor)
    editor.logger = _Logger()
    editor.config = _Config()
    editor.repo = _Repo()
    editor.grouping = _Grouping()
    editor.video_editor = _VideoEditor()
    editor.progress = progress
    editor._cancelled = True
    editor._state = EditingState()

    class _EditResult(os.PathLike[str]):
        def __init__(self, target: Path, metadata: dict[str, str]) -> None:
            self._target = target
            self._metadata = metadata

        def __fspath__(self) -> str:
            return str(self._target)

        def __iter__(self) -> Iterator[Path | dict[str, str]]:
            yield self._target
            yield self._metadata

    async def fake_edit(
        idx: int,
        day: datetime.date,
        time_slot: datetime.time,
        match_name: str,
        rule_name: str,
        group: list[object],
    ) -> _EditResult:
        _ = idx, day, time_slot, match_name, rule_name, group
        return _EditResult(
            edited_video,
            {
                "title": generated_title,
                "description": "description",
            },
        )

    editor._edit = fake_edit

    await editor.execute()

    assert editor._cancelled is False
    assert any(
        call["task_id"] == "auto_edit"
        and call["item_index"] == 0
        and call["stage_key"] == "save"
        and call["stage_label"] == "録画済動画削除・編集済動画保存"
        for call in progress.item_stage_calls
    )
    assert deleted_videos == [source_video]
