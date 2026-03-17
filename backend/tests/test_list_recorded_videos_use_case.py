"""ListRecordedVideosUseCase のテスト。

責務：
- 録画ビデオ一覧取得フローの検証
- メタデータフィルタリング
- DTO変換
- エラーハンドリング

分類: logic
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from splat_replay.application.dto import RecordedVideoDTO
from splat_replay.application.use_cases.assets.list_recorded_videos import (
    ListRecordedVideosUseCase,
)
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
)
from splat_replay.domain.models.video_asset import VideoAsset


@pytest.fixture
def base_dir(tmp_path):
    """一時ベースディレクトリ。"""
    return tmp_path


@pytest.fixture
def mock_repository():
    """VideoAssetRepositoryPortのモック。"""
    return MagicMock()


@pytest.fixture
def mock_logger():
    """LoggerPortのモック。"""
    return MagicMock()


@pytest.fixture
def mock_video_editor():
    """VideoEditorPortのモック。"""
    editor = AsyncMock()
    # get_duration と get_file_size のデフォルト値
    editor.get_duration.return_value = 300.0
    editor.get_file_size.return_value = 1024000
    return editor


@pytest.fixture
def use_case(mock_repository, mock_logger, base_dir, mock_video_editor):
    """ListRecordedVideosUseCaseのインスタンス。"""
    return ListRecordedVideosUseCase(
        repository=mock_repository,
        logger=mock_logger,
        base_dir=base_dir,
        video_editor=mock_video_editor,
    )


@pytest.fixture
def battle_metadata():
    """バトルメタデータのサンプル。"""
    return RecordingMetadata(
        game_mode=GameMode.BATTLE,
        result=BattleResult(
            match=Match.REGULAR,
            rule=Rule.TURF_WAR,
            stage=Stage.SCORCH_GORGE,
            kill=5,
            death=3,
            special=2,
        ),
    )


class TestListRecordedVideosHappyPath:
    """正常系のテスト。"""

    @pytest.mark.asyncio
    async def test_list_empty_recordings(self, use_case, mock_repository):
        """録画が1つもない場合は空リストを返す。"""
        mock_repository.list_recordings.return_value = []

        result = await use_case.execute()

        assert result == []
        mock_repository.list_recordings.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_single_recording(
        self, use_case, base_dir, mock_repository, battle_metadata
    ):
        """録画が1つある場合は1件のDTOを返す。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        asset = VideoAsset(video=video_path, metadata=battle_metadata)
        mock_repository.list_recordings.return_value = [asset]

        # has_subtitle と has_thumbnail の戻り値も設定
        mock_repository.has_subtitle.return_value = False
        mock_repository.has_thumbnail.return_value = True

        result = await use_case.execute()

        assert len(result) == 1
        assert isinstance(result[0], RecordedVideoDTO)
        assert result[0].filename == "test.mp4"

    @pytest.mark.asyncio
    async def test_list_multiple_recordings(
        self, use_case, base_dir, mock_repository, battle_metadata
    ):
        """複数の録画がある場合は全件のDTOを返す。"""
        videos = []
        for i in range(3):
            video_path = base_dir / "recorded" / f"test{i}.mp4"
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.touch()
            videos.append(
                VideoAsset(video=video_path, metadata=battle_metadata)
            )

        mock_repository.list_recordings.return_value = videos
        mock_repository.has_subtitle.return_value = False
        mock_repository.has_thumbnail.return_value = True

        result = await use_case.execute()

        assert len(result) == 3
        assert all(isinstance(dto, RecordedVideoDTO) for dto in result)


class TestListRecordedVideosFiltering:
    """メタデータフィルタリングのテスト。"""

    @pytest.mark.asyncio
    async def test_skip_assets_without_metadata(
        self, use_case, base_dir, mock_repository, mock_logger, battle_metadata
    ):
        """メタデータが無いアセットはスキップされる。"""
        video1 = base_dir / "recorded" / "with_meta.mp4"
        video2 = base_dir / "recorded" / "without_meta.mp4"
        video1.parent.mkdir(parents=True)
        video1.touch()
        video2.touch()

        assets = [
            VideoAsset(video=video1, metadata=battle_metadata),
            VideoAsset(video=video2, metadata=None),  # メタデータなし
        ]
        mock_repository.list_recordings.return_value = assets
        mock_repository.has_subtitle.return_value = False
        mock_repository.has_thumbnail.return_value = True

        result = await use_case.execute()

        # メタデータありの1件のみ返される
        assert len(result) == 1
        assert result[0].filename == "with_meta.mp4"

        # 警告ログが記録される
        mock_logger.warning.assert_called_once()
        assert "メタデータが無い" in str(mock_logger.warning.call_args)

    @pytest.mark.asyncio
    async def test_all_assets_without_metadata(
        self, use_case, base_dir, mock_repository, mock_logger
    ):
        """全アセットがメタデータなしの場合は空リストを返す。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        assets = [VideoAsset(video=video_path, metadata=None)]
        mock_repository.list_recordings.return_value = assets

        result = await use_case.execute()

        assert result == []
        mock_logger.warning.assert_called()


class TestListRecordedVideosIntegration:
    """統合動作のテスト。"""

    @pytest.mark.asyncio
    async def test_dto_mapping_includes_all_fields(
        self,
        use_case,
        base_dir,
        mock_repository,
        mock_video_editor,
        battle_metadata,
    ):
        """DTOに全フィールドがマッピングされる。"""
        video_path = base_dir / "recorded" / "full_test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        asset = VideoAsset(video=video_path, metadata=battle_metadata)
        mock_repository.list_recordings.return_value = [asset]
        mock_repository.has_subtitle.return_value = True
        mock_repository.has_thumbnail.return_value = True
        mock_video_editor.get_video_length.return_value = 123.45
        file_stats = type("FileStats", (), {"size_bytes": 999888})()
        mock_repository.get_file_stats.return_value = file_stats

        result = await use_case.execute()

        dto = result[0]
        assert dto.filename == "full_test.mp4"
        assert dto.has_subtitle is True
        assert dto.has_thumbnail is True
        assert dto.duration_seconds == 123.45
        assert dto.size_bytes == 999888
        assert dto.game_mode == "BATTLE"

    @pytest.mark.asyncio
    async def test_repository_called_correctly(
        self, use_case, mock_repository, battle_metadata, base_dir
    ):
        """リポジトリメソッドが正しく呼ばれる。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        asset = VideoAsset(video=video_path, metadata=battle_metadata)
        mock_repository.list_recordings.return_value = [asset]
        mock_repository.has_subtitle.return_value = False
        mock_repository.has_thumbnail.return_value = False

        await use_case.execute()

        # list_recordings が1回呼ばれる
        mock_repository.list_recordings.assert_called_once()

        # has_subtitle と has_thumbnail が各アセットに対して呼ばれる
        assert mock_repository.has_subtitle.called
        assert mock_repository.has_thumbnail.called
