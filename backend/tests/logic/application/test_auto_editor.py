from __future__ import annotations

from collections.abc import Iterator
import datetime
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from splat_replay.application.services.editing.auto_editor import AutoEditor
from splat_replay.application.services.editing.editing_state import (
    EditingState,
)


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

    assert any(
        call["task_id"] == "auto_edit"
        and call["item_index"] == 0
        and call["stage_key"] == "save"
        and call["stage_label"] == "録画済動画削除・編集済動画保存"
        for call in progress.item_stage_calls
    )
    assert deleted_videos == [source_video]
