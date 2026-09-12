from __future__ import annotations

from collections.abc import Iterator
import datetime
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from splat_replay.application.services.editing.auto_editor import (
    AutoEditor,
    EditedCommitCleanupError,
    SOURCE_RECORDINGS_METADATA_KEY,
)
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
        cancel_check=None,
    ) -> None:
        _ = cancel_check
        self.combined_calls.append((path, metadata, thumbnail))
        on_progress(33.0, "埋め込み中")

    async def embed_metadata(
        self, path: Path, metadata: dict[str, str], *, cancel_check=None
    ) -> None:
        _ = cancel_check
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
    ) -> bool:
        self.metadata_calls.append((target, metadata))
        return True

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
    editor._cancelled = False

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

        def get_edited_dir(self) -> Path:
            return tmp_path / "committed"

        def list_edited(self) -> list[Path]:
            return []

        def save_edited(self, target: Path) -> Path:
            return target

        def delete_recording(self, video: Path) -> bool:
            deleted_videos.append(video)
            return True

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
    editor._cancelled = False
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


def test_make_filename_is_stable_for_same_inputs(tmp_path: Path) -> None:
    editor = AutoEditor.__new__(AutoEditor)
    assets = [
        SimpleNamespace(video=tmp_path / "b.mkv"),
        SimpleNamespace(video=tmp_path / "a.mkv"),
    ]

    first = editor._make_filename(
        assets,
        datetime.date(2026, 8, 13),
        datetime.time(20, 0),
        "Xマッチ",
        "ガチエリア",
    )
    second = editor._make_filename(
        list(reversed(assets)),
        datetime.date(2026, 8, 13),
        datetime.time(20, 0),
        "Xマッチ",
        "ガチエリア",
    )

    assert first.name == second.name
    assert first.name.startswith("20260813_20_Xマッチ_ガチエリア_")
    assert first.suffix == ".mkv"


@pytest.mark.asyncio
async def test_committed_manifest_recovers_partial_cleanup_without_reediting(
    tmp_path: Path,
) -> None:
    remaining = SimpleNamespace(
        video=tmp_path / "recorded" / "second.mkv",
        metadata=None,
    )
    committed = tmp_path / "edited" / "combined.mkv"
    deleted: list[Path] = []

    class _Logger:
        def info(self, *args: object, **kwargs: object) -> None:
            _ = args, kwargs

    class _Config:
        def get_video_edit_settings(self) -> object:
            return object()

    class _Grouping:
        def group_by_timeslot(
            self, assets: list[object]
        ) -> dict[object, object]:
            assert assets == []
            return {}

    class _Repo:
        def list_recordings(self) -> list[object]:
            return [remaining]

        def list_edited(self) -> list[Path]:
            return [committed]

        def get_edited_metadata(self, video: Path) -> dict[str, str]:
            assert video == committed
            return {
                SOURCE_RECORDINGS_METADATA_KEY: ('["first.mkv", "second.mkv"]')
            }

        def delete_recording(self, video: Path) -> bool:
            deleted.append(video)
            return True

    editor = AutoEditor.__new__(AutoEditor)
    editor.logger = _Logger()
    editor.config = _Config()
    editor.repo = _Repo()
    editor.grouping = _Grouping()
    editor.progress = _FakeProgress()
    editor._cancelled = False
    editor._state = EditingState()

    result = await editor.execute()

    assert result == [committed]
    assert deleted == [remaining.video]


@pytest.mark.asyncio
async def test_metadata_save_failure_is_reported(tmp_path: Path) -> None:
    class _Repo:
        def save_edited_metadata_dict(
            self, target: Path, metadata: dict[str, str]
        ) -> bool:
            _ = target, metadata
            return False

    editor = AutoEditor.__new__(AutoEditor)
    editor.repo = _Repo()
    target = tmp_path / "edited.mkv"

    with pytest.raises(RuntimeError, match="メタデータを保存できませんでした"):
        await editor._save_metadata_sidecar(target, {"title": "title"})


@pytest.mark.asyncio
async def test_committed_edit_cleanup_failure_stops_before_upload(
    tmp_path: Path,
) -> None:
    source_video = tmp_path / "source.mkv"
    asset = SimpleNamespace(video=source_video, metadata=None)
    key = (
        datetime.date(2026, 8, 13),
        datetime.time(20, 0),
        "Xマッチ",
        "ガチエリア",
    )

    class _Logger:
        def info(self, *args: object, **kwargs: object) -> None:
            _ = args, kwargs

    class _Config:
        def get_video_edit_settings(self) -> object:
            return object()

    class _Grouping:
        def group_by_timeslot(
            self, assets: list[object]
        ) -> dict[tuple[object, ...], list[object]]:
            return {key: assets}

    editor = AutoEditor.__new__(AutoEditor)
    editor.logger = _Logger()
    editor.config = _Config()
    editor.grouping = _Grouping()
    editor.progress = _FakeProgress()
    editor._cancelled = False
    editor._state = EditingState()
    committed = tmp_path / "edited" / editor._make_filename([asset], *key).name

    class _Repo:
        def list_recordings(self) -> list[object]:
            return [asset]

        def get_edited_dir(self) -> Path:
            return committed.parent

        def list_edited(self) -> list[Path]:
            return [committed]

        def get_edited_metadata(self, video: Path) -> dict[str, str] | None:
            _ = video
            return None

        def delete_recording(self, video: Path) -> bool:
            _ = video
            return False

    editor.repo = _Repo()

    with pytest.raises(EditedCommitCleanupError):
        await editor.execute()

    assert editor.progress.start_task_calls == []


def _build_cancellable_editor(
    tmp_path: Path,
) -> tuple[
    AutoEditor,
    Any,
    Path,
    Path,
    tuple[datetime.date, datetime.time, str, str],
]:
    source = tmp_path / "recorded" / "source.mkv"
    source.parent.mkdir()
    source.write_bytes(b"source")
    edited_dir = tmp_path / "edited"
    edited_dir.mkdir()
    asset = SimpleNamespace(video=source, metadata=None)
    key = (
        datetime.date(2026, 9, 4),
        datetime.time(7, 0),
        "Xマッチ",
        "ガチエリア",
    )

    editor = AutoEditor.__new__(AutoEditor)
    editor.logger = MagicMock()
    editor.config = SimpleNamespace(
        get_video_edit_settings=lambda: SimpleNamespace()
    )
    editor.grouping = SimpleNamespace(
        group_by_timeslot=lambda assets: {key: assets}
    )
    editor.video_editor = SimpleNamespace(
        get_video_length=AsyncMock(return_value=180.0)
    )
    editor.progress = _FakeProgress()
    editor._file_system = _FakeFileSystem()
    editor._cancelled = False
    editor._state = EditingState()
    return editor, asset, source, edited_dir, key


@pytest.mark.asyncio
@pytest.mark.parametrize("partial_success", [False, True])
async def test_edit_failure_blocks_upload_and_reports_failure(
    tmp_path: Path,
    partial_success: bool,
) -> None:
    """グループ失敗を成功通知にせず、成功した成果物は保持する。"""
    from splat_replay.application.use_cases.assets.start_edit_upload import (
        StartEditUploadUseCase,
    )

    editor, asset, source, edited_dir, key = _build_cancellable_editor(
        tmp_path
    )
    repo = MagicMock()
    repo.list_recordings.return_value = [asset]
    repo.list_edited.return_value = []
    repo.get_edited_dir.return_value = edited_dir
    editor.repo = repo
    edit = AsyncMock(side_effect=OSError("cannot open resource"))
    committed = edited_dir / "completed.mkv"
    if partial_success:
        second_source = source.with_name("second.mkv")
        second_source.write_bytes(b"second")
        second_asset = SimpleNamespace(video=second_source, metadata=None)
        second_key = (key[0], datetime.time(9), key[2], key[3])
        editor.grouping = SimpleNamespace(
            group_by_timeslot=lambda assets: {
                key: assets,
                second_key: [second_asset],
            }
        )
        committed.write_bytes(b"completed")
        edit.side_effect = [OSError("cannot open resource"), (committed, {})]
        repo.save_edited.return_value = committed
    editor._edit = edit  # type: ignore[invalid-assignment]
    uploader = MagicMock(execute=AsyncMock())
    event_bus = MagicMock()
    config = MagicMock()
    config.get_behavior_settings.return_value.sleep_after_upload = False
    use_case = StartEditUploadUseCase(
        editor, uploader, event_bus, config, MagicMock()
    )

    await use_case.execute()
    with pytest.raises(RuntimeError, match="cannot open resource"):
        await use_case.wait_until_complete()

    assert edit.await_count == (2 if partial_success else 1)
    assert source.read_bytes() == b"source"
    assert editor.get_status()["phase"] == "failed"
    assert isinstance(editor.progress, _FakeProgress)
    assert editor.progress.finish_calls[-1]["success"] is False
    assert use_case.get_state() == "failed"
    uploader.execute.assert_not_awaited()
    completion = event_bus.publish_domain_event.call_args.args[0]
    assert completion.success is False
    if partial_success:
        assert committed.read_bytes() == b"completed"
    else:
        repo.save_edited.assert_not_called()
        repo.delete_recording.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_before_commit_keeps_recording_and_removes_outputs(
    tmp_path: Path,
) -> None:
    editor, asset, source, edited_dir, key = _build_cancellable_editor(
        tmp_path
    )
    repo = MagicMock()
    repo.list_recordings.return_value = [asset]
    repo.list_edited.return_value = []
    repo.get_edited_dir.return_value = edited_dir
    editor.repo = repo
    target = editor._make_filename([asset], *key)

    async def cancel_before_commit(
        *args: object,
    ) -> tuple[Path, dict[str, str]]:
        _ = args
        target.write_bytes(b"uncommitted")
        target.with_suffix(".json").write_text("{}", encoding="utf-8")
        (edited_dir / target.name).with_suffix(".png").write_bytes(b"preview")
        editor.request_cancel()
        return target, {"title": "cancelled"}

    editor._edit = cancel_before_commit  # type: ignore[invalid-assignment]

    result = await editor.execute()

    assert result == []
    assert source.read_bytes() == b"source"
    assert not target.exists()
    assert not target.with_suffix(".json").exists()
    assert not (edited_dir / target.name).with_suffix(".png").exists()
    repo.save_edited.assert_not_called()
    repo.delete_recording.assert_not_called()
    assert editor.get_status()["phase"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_after_commit_finishes_recording_cleanup(
    tmp_path: Path,
) -> None:
    editor, asset, source, edited_dir, key = _build_cancellable_editor(
        tmp_path
    )
    repo = MagicMock()
    repo.list_recordings.return_value = [asset]
    repo.list_edited.return_value = []
    repo.get_edited_dir.return_value = edited_dir
    editor.repo = repo
    target = editor._make_filename([asset], *key)
    committed = edited_dir / target.name

    async def finish_edit(*args: object) -> tuple[Path, dict[str, str]]:
        _ = args
        target.write_bytes(b"edited")
        return target, {"title": "committed"}

    def commit_and_cancel(path: Path) -> Path:
        path.replace(committed)
        editor.request_cancel()
        return committed

    def delete_recording(path: Path) -> bool:
        path.unlink()
        return True

    editor._edit = finish_edit  # type: ignore[invalid-assignment]
    repo.save_edited.side_effect = commit_and_cancel
    repo.delete_recording.side_effect = delete_recording

    result = await editor.execute()

    assert result == [committed]
    assert committed.read_bytes() == b"edited"
    assert not source.exists()
    repo.delete_recording.assert_called_once_with(source)
    assert editor.get_status()["phase"] == "cancelled"
