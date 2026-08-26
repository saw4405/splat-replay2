from __future__ import annotations

import shutil
from pathlib import Path
from typing import cast

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.domain.config import VideoStorageSettings
from splat_replay.infrastructure.repositories.asset_file_operations import (
    AssetEventPublisher,
    AssetFileOperations,
)
from splat_replay.infrastructure.repositories.edited_asset_repo import (
    EditedAssetRepository,
)


class _Logger:
    def debug(self, event: str, **kw: object) -> None:
        _ = event, kw

    def info(self, event: str, **kw: object) -> None:
        _ = event, kw

    def warning(self, event: str, **kw: object) -> None:
        _ = event, kw

    def error(self, event: str, **kw: object) -> None:
        _ = event, kw

    def exception(self, event: str, **kw: object) -> None:
        _ = event, kw


class _Publisher:
    def __init__(self) -> None:
        self.events: list[object] = []

    def publish_domain_event(self, event: object) -> None:
        self.events.append(event)


def _build_repository(
    tmp_path: Path,
) -> tuple[EditedAssetRepository, _Publisher, VideoStorageSettings]:
    logger = cast(BoundLogger, _Logger())
    publisher = _Publisher()
    settings = VideoStorageSettings(base_dir=tmp_path / "videos")
    repository = EditedAssetRepository(
        settings=settings,
        logger=logger,
        file_ops=AssetFileOperations(logger),
        event_publisher=AssetEventPublisher(publisher),
    )
    return repository, publisher, settings


def test_save_edited_publishes_video_after_sidecars(tmp_path: Path) -> None:
    repository, publisher, settings = _build_repository(tmp_path)
    video = tmp_path / "work.mp4"
    video.write_bytes(b"video")
    video.with_suffix(".json").write_text("{}", encoding="utf-8")

    committed = repository.save_edited(video)

    assert committed == settings.edited_dir / "work.mp4"
    assert committed.read_bytes() == b"video"
    assert committed.with_suffix(".json").read_text(encoding="utf-8") == "{}"
    assert not video.exists()
    assert len(publisher.events) == 1


def test_save_edited_rolls_back_sidecars_when_video_move_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository, publisher, settings = _build_repository(tmp_path)
    video = tmp_path / "work.mp4"
    sidecar = video.with_suffix(".json")
    video.write_bytes(b"video")
    sidecar.write_text("{}", encoding="utf-8")
    real_move = shutil.move

    def fail_video_move(source: str, destination: Path) -> str:
        if Path(source) == video:
            raise OSError("video move failed")
        return str(real_move(source, destination))

    monkeypatch.setattr(
        "splat_replay.infrastructure.repositories.edited_asset_repo.shutil.move",
        fail_video_move,
    )

    with pytest.raises(OSError, match="video move failed"):
        repository.save_edited(video)

    assert video.exists()
    assert sidecar.exists()
    assert not (settings.edited_dir / video.name).exists()
    assert not (settings.edited_dir / sidecar.name).exists()
    assert publisher.events == []
