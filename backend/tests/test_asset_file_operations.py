"""AssetFileOperations のテスト。

責務：
- ファイル名生成
- 字幕・サムネイル・メタデータの読み書き
- ファイルパス管理

分類: logic
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import cast

import cv2
import numpy as np
import pytest
from structlog.stdlib import BoundLogger

from splat_replay.domain.models import (
    BattleResult,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
)
from splat_replay.infrastructure.repositories.asset_file_operations import (
    AssetFileOperations,
)


class _DummyLogger:
    def debug(self, event: str, **kw: object) -> None:
        pass

    def info(self, event: str, **kw: object) -> None:
        pass

    def warning(self, event: str, **kw: object) -> None:
        pass

    def error(self, event: str, **kw: object) -> None:
        pass

    def exception(self, event: str, **kw: object) -> None:
        pass


@pytest.fixture
def file_ops() -> AssetFileOperations:
    """AssetFileOperationsのインスタンス。"""
    logger = cast(BoundLogger, _DummyLogger())
    return AssetFileOperations(logger)


class TestAssetFileOperationsFilenameGeneration:
    """ファイル名生成のテスト。"""

    def test_generate_filename_with_minimal_metadata(
        self, file_ops: AssetFileOperations
    ) -> None:
        """最小限のメタデータからファイル名を生成できる。"""
        metadata = RecordingMetadata(
            started_at=datetime(2026, 3, 14, 10, 30, 45)
        )

        filename = file_ops.generate_filename(metadata)

        assert filename == "20260314_103045"

    def test_generate_filename_with_battle_metadata(
        self, file_ops: AssetFileOperations
    ) -> None:
        """対戦メタデータを含むファイル名を生成できる。"""
        metadata = RecordingMetadata(
            started_at=datetime(2026, 3, 14, 10, 30, 45),
            result=BattleResult(
                match=Match.REGULAR,
                rule=Rule.TURF_WAR,
                stage=Stage.SCORCH_GORGE,
                kill=10,
                death=5,
                special=3,
            ),
            judgement=Judgement.WIN,
        )

        filename = file_ops.generate_filename(metadata)

        assert (
            filename
            == "20260314_103045_レギュラーマッチ_ナワバリ_WIN_ユノハナ大渓谷"
        )

    def test_generate_filename_with_partial_battle_metadata(
        self, file_ops: AssetFileOperations
    ) -> None:
        """一部の対戦メタデータを含むファイル名を生成できる。"""
        metadata = RecordingMetadata(
            started_at=datetime(2026, 3, 14, 10, 30, 45),
            result=BattleResult(
                match=Match.ANARCHY,
                rule=None,
                stage=None,
                kill=0,
                death=0,
                special=0,
            ),
            judgement=None,
        )

        filename = file_ops.generate_filename(metadata)

        assert filename == "20260314_103045_バンカラマッチ"

    def test_generate_filename_raises_when_started_at_is_none(
        self, file_ops: AssetFileOperations
    ) -> None:
        """started_atがNoneの場合にValueErrorが発生する。"""
        metadata = RecordingMetadata(started_at=None)

        with pytest.raises(
            ValueError, match="must have a started_at timestamp"
        ):
            file_ops.generate_filename(metadata)


class TestAssetFileOperationsSubtitle:
    """字幕ファイル操作のテスト。"""

    def test_save_subtitle_creates_file(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """字幕ファイルが作成される。"""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")

        result = file_ops.save_subtitle(video, "Subtitle content")

        assert result is True
        assert video.with_suffix(".srt").exists()
        assert (
            video.with_suffix(".srt").read_text(encoding="utf-8")
            == "Subtitle content"
        )

    def test_save_subtitle_creates_parent_directory(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """親ディレクトリが存在しない場合は作成される。"""
        video = tmp_path / "subdir" / "video.mp4"

        result = file_ops.save_subtitle(video, "Subtitle content")

        assert result is True
        assert video.with_suffix(".srt").exists()

    def test_load_subtitle_returns_content(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """字幕内容が取得できる。"""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        file_ops.save_subtitle(video, "Test subtitle")

        content = file_ops.load_subtitle(video)

        assert content == "Test subtitle"

    def test_load_subtitle_returns_none_if_missing(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """字幕ファイルが存在しない場合はNoneを返す。"""
        video = tmp_path / "video.mp4"

        content = file_ops.load_subtitle(video)

        assert content is None


class TestAssetFileOperationsThumbnail:
    """サムネイルファイル操作のテスト。"""

    def test_save_thumbnail_creates_file(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """サムネイルファイルが作成される。"""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        result = file_ops.save_thumbnail(video, frame)

        assert result is True
        assert video.with_suffix(".png").exists()

    def test_save_thumbnail_creates_parent_directory(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """親ディレクトリが存在しない場合は作成される。"""
        video = tmp_path / "subdir" / "video.mp4"
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        result = file_ops.save_thumbnail(video, frame)

        assert result is True
        assert video.with_suffix(".png").exists()

    def test_load_thumbnail_returns_frame(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """サムネイル画像が取得できる。"""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        file_ops.save_thumbnail(video, frame)

        loaded = file_ops.load_thumbnail(video)

        assert loaded is not None
        assert isinstance(loaded, bytes)
        # bytesからnumpy配列にデコードして形状確認
        decoded = cv2.imdecode(
            np.frombuffer(loaded, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        assert decoded is not None
        assert decoded.shape == (100, 100, 3)

    def test_load_thumbnail_returns_none_if_missing(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """サムネイルファイルが存在しない場合はNoneを返す。"""
        video = tmp_path / "video.mp4"

        loaded = file_ops.load_thumbnail(video)

        assert loaded is None


class TestAssetFileOperationsMetadata:
    """メタデータファイル操作のテスト。"""

    def test_save_metadata_creates_file(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """メタデータファイルが作成される。"""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        metadata = RecordingMetadata(
            started_at=datetime(2026, 3, 14, 10, 30, 45)
        )

        result = file_ops.save_metadata(video, metadata)

        assert result is True
        assert video.with_suffix(".json").exists()

    def test_save_metadata_creates_parent_directory(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """親ディレクトリが存在しない場合は作成される。"""
        video = tmp_path / "subdir" / "video.mp4"
        metadata = RecordingMetadata(
            started_at=datetime(2026, 3, 14, 10, 30, 45)
        )

        result = file_ops.save_metadata(video, metadata)

        assert result is True
        assert video.with_suffix(".json").exists()

    def test_load_metadata_dict_returns_dict(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """メタデータ辞書が取得できる。"""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        metadata = RecordingMetadata(
            started_at=datetime(2026, 3, 14, 10, 30, 45)
        )
        file_ops.save_metadata(video, metadata)

        loaded = file_ops.load_metadata_dict(video)

        assert loaded is not None
        assert "started_at" in loaded

    def test_load_metadata_dict_returns_none_if_missing(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """メタデータファイルが存在しない場合はNoneを返す。"""
        video = tmp_path / "video.mp4"

        loaded = file_ops.load_metadata_dict(video)

        assert loaded is None


class TestAssetFileOperationsDeleteRelatedFiles:
    """関連ファイル削除のテスト。"""

    def test_delete_related_files_removes_all_files(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """字幕・サムネイル・メタデータが削除される。"""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")

        # 関連ファイルを作成
        file_ops.save_subtitle(video, "subtitle")
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        file_ops.save_thumbnail(video, frame)
        metadata = RecordingMetadata(
            started_at=datetime(2026, 3, 14, 10, 30, 45)
        )
        file_ops.save_metadata(video, metadata)

        file_ops.delete_related_files(video)

        assert not video.with_suffix(".srt").exists()
        assert not video.with_suffix(".png").exists()
        assert not video.with_suffix(".json").exists()

    def test_delete_related_files_does_not_fail_if_files_missing(
        self, file_ops: AssetFileOperations, tmp_path: Path
    ) -> None:
        """関連ファイルが存在しなくてもエラーにならない。"""
        video = tmp_path / "video.mp4"

        # エラーなく完了すること
        file_ops.delete_related_files(video)

        assert True
