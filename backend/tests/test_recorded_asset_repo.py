from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from structlog.stdlib import BoundLogger

from splat_replay.domain.config import VideoStorageSettings
from splat_replay.domain.models import RecordingMetadata
from splat_replay.infrastructure.repositories.asset_file_operations import (
    AssetEventPublisher,
    AssetFileOperations,
)
from splat_replay.infrastructure.repositories.recorded_asset_repo import (
    RecordedAssetRepository,
)


class _DummyLogger:
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


class _DomainEventPublisherSpy:
    def __init__(self) -> None:
        self.events: list[object] = []

    def publish_domain_event(self, event: object) -> None:
        self.events.append(event)


def _build_repository(
    tmp_path: Path,
) -> tuple[
    RecordedAssetRepository,
    _DomainEventPublisherSpy,
    VideoStorageSettings,
]:
    logger = cast(BoundLogger, _DummyLogger())
    settings = VideoStorageSettings(base_dir=tmp_path / "videos")
    publisher = _DomainEventPublisherSpy()
    repository = RecordedAssetRepository(
        settings=settings,
        logger=logger,
        file_ops=AssetFileOperations(logger),
        event_publisher=AssetEventPublisher(publisher),
    )
    return repository, publisher, settings


def _metadata() -> RecordingMetadata:
    return RecordingMetadata(started_at=datetime(2026, 3, 8, 14, 19, 56))


def test_save_recording_raises_when_video_move_fails_and_does_not_publish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository, publisher, settings = _build_repository(tmp_path)
    video = tmp_path / "capture.mp4"
    video.write_bytes(b"video")
    subtitle = tmp_path / "capture.srt"
    subtitle.write_text("subtitle", encoding="utf-8")

    def _raise_move(_src: str, _dest: Path) -> None:
        raise OSError("move failed")

    monkeypatch.setattr(
        "splat_replay.infrastructure.repositories.recorded_asset_repo.shutil.move",
        _raise_move,
    )

    with pytest.raises(OSError, match="move failed"):
        repository.save_recording(video, subtitle, None, _metadata())

    assert video.exists()
    assert subtitle.exists()
    assert list(settings.recorded_dir.glob("*")) == []
    assert publisher.events == []


def test_save_recording_rolls_back_moved_files_when_metadata_save_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository, publisher, settings = _build_repository(tmp_path)
    video = tmp_path / "capture.mp4"
    video.write_bytes(b"video")
    subtitle = tmp_path / "capture.srt"
    subtitle.write_text("subtitle", encoding="utf-8")

    def _fail_save_metadata(
        _base_path: Path,
        _metadata: RecordingMetadata,
    ) -> bool:
        return False

    monkeypatch.setattr(
        repository._file_ops,
        "save_metadata",
        _fail_save_metadata,
    )

    with pytest.raises(RuntimeError, match="メタデータの保存に失敗しました"):
        repository.save_recording(video, subtitle, None, _metadata())

    assert video.exists()
    assert subtitle.exists()
    assert list(settings.recorded_dir.glob("*")) == []
    assert publisher.events == []


def test_save_recording_succeeds_with_video_only(tmp_path: Path) -> None:
    """動画のみの保存が成功する。"""
    repository, publisher, settings = _build_repository(tmp_path)
    video = tmp_path / "capture.mp4"
    video.write_bytes(b"video content")

    result = repository.save_recording(video, None, None, _metadata())

    assert result.video.exists()
    assert result.video.parent == settings.recorded_dir
    assert not video.exists()
    assert len(publisher.events) == 1


def test_save_recording_succeeds_with_video_and_subtitle(
    tmp_path: Path,
) -> None:
    """動画と字幕の保存が成功する。"""
    repository, publisher, settings = _build_repository(tmp_path)
    video = tmp_path / "capture.mp4"
    video.write_bytes(b"video content")
    subtitle = tmp_path / "capture.srt"
    subtitle.write_text("subtitle content", encoding="utf-8")

    result = repository.save_recording(video, subtitle, None, _metadata())

    assert result.video.exists()
    assert result.subtitle is not None and result.subtitle.exists()
    assert not video.exists()
    assert not subtitle.exists()


def test_save_recording_succeeds_with_video_and_thumbnail(
    tmp_path: Path,
) -> None:
    """動画とサムネイルの保存が成功する。"""
    repository, publisher, settings = _build_repository(tmp_path)
    video = tmp_path / "capture.mp4"
    video.write_bytes(b"video content")
    thumbnail_data = np.zeros((100, 100, 3), dtype=np.uint8)

    result = repository.save_recording(
        video, None, thumbnail_data, _metadata()
    )

    assert result.video.exists()
    assert result.thumbnail is not None and result.thumbnail.exists()
    assert not video.exists()


def test_save_recording_succeeds_with_all_files(tmp_path: Path) -> None:
    """動画、字幕、サムネイルすべての保存が成功する。"""
    repository, publisher, settings = _build_repository(tmp_path)
    video = tmp_path / "capture.mp4"
    video.write_bytes(b"video content")
    subtitle = tmp_path / "capture.srt"
    subtitle.write_text("subtitle content", encoding="utf-8")
    thumbnail_data = np.zeros((100, 100, 3), dtype=np.uint8)

    result = repository.save_recording(
        video, subtitle, thumbnail_data, _metadata()
    )

    assert result.video.exists()
    assert result.subtitle is not None and result.subtitle.exists()
    assert result.thumbnail is not None and result.thumbnail.exists()
    assert result.metadata is not None
    assert not video.exists()
    assert not subtitle.exists()


def test_list_recorded_returns_empty_list_initially(tmp_path: Path) -> None:
    """初期状態では空のリストを返す。"""
    repository, _, _ = _build_repository(tmp_path)

    videos = repository.list_recordings()

    assert len(videos) == 0


def test_list_recorded_returns_mp4_and_mkv_files(tmp_path: Path) -> None:
    """*.mp4と*.mkvの両方を返す。"""
    repository, _, settings = _build_repository(tmp_path)
    settings.recorded_dir.mkdir(parents=True, exist_ok=True)
    (settings.recorded_dir / "video1.mp4").write_bytes(b"fake")
    (settings.recorded_dir / "video2.mkv").write_bytes(b"fake")
    (settings.recorded_dir / "other.txt").write_text(
        "ignore", encoding="utf-8"
    )

    videos = repository.list_recordings()

    assert len(videos) == 2
    # VideoAssetオブジェクトのvideoパスから名前を取得
    video_names = {v.video.name for v in videos}
    assert video_names == {"video1.mp4", "video2.mkv"}


def test_delete_recorded_removes_all_files(tmp_path: Path) -> None:
    """動画と関連ファイルがすべて削除される。"""
    repository, publisher, settings = _build_repository(tmp_path)
    settings.recorded_dir.mkdir(parents=True, exist_ok=True)
    video = settings.recorded_dir / "video.mp4"
    video.write_bytes(b"fake")
    video.with_suffix(".srt").write_text("subtitle", encoding="utf-8")
    video.with_suffix(".png").write_bytes(b"image")
    video.with_suffix(".json").write_text("{}", encoding="utf-8")

    result = repository.delete_recording(video)

    assert result is True
    assert not video.exists()
    assert not video.with_suffix(".srt").exists()
    assert not video.with_suffix(".png").exists()
    assert not video.with_suffix(".json").exists()
    assert len(publisher.events) == 1


def test_get_subtitle_returns_content(tmp_path: Path) -> None:
    """字幕内容が取得できる。"""
    repository, _, settings = _build_repository(tmp_path)
    settings.recorded_dir.mkdir(parents=True, exist_ok=True)
    video = settings.recorded_dir / "video.mp4"
    video.write_bytes(b"fake")
    repository.save_subtitle(video, "Test subtitle")

    content = repository.get_subtitle(video)

    assert content == "Test subtitle"


def test_get_subtitle_returns_none_if_missing(tmp_path: Path) -> None:
    """字幕ファイルが存在しない場合はNoneを返す。"""
    repository, _, settings = _build_repository(tmp_path)
    settings.recorded_dir.mkdir(parents=True, exist_ok=True)
    video = settings.recorded_dir / "video.mp4"

    content = repository.get_subtitle(video)

    assert content is None
