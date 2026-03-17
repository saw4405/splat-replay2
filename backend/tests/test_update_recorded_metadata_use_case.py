"""UpdateRecordedMetadataUseCase のテスト。

責務：
- メタデータ更新フローの検証
- バリデーション（ゲームモード整合性、必須フィールド）
- リポジトリとの統合
- エラーハンドリング

分類: logic
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from splat_replay.application.dto import RecordedVideoDTO
from splat_replay.application.dto.metadata import RecordingMetadataPatchDTO
from splat_replay.application.use_cases.metadata.update_recorded_metadata import (
    UpdateRecordedMetadataUseCase,
)
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    Match,
    RecordingMetadata,
    Rule,
    SalmonResult,
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
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_logger():
    """LoggerPortのモック。"""
    return MagicMock()


@pytest.fixture
def mock_video_editor():
    """VideoEditorPortのモック。"""
    return AsyncMock()


@pytest.fixture
def mock_battle_history_service():
    """BattleHistoryServiceのモック。"""
    service = MagicMock()
    return service


@pytest.fixture
def use_case(
    mock_repository,
    mock_logger,
    base_dir,
    mock_video_editor,
    mock_battle_history_service,
):
    """UpdateRecordedMetadataUseCaseのインスタンス。"""
    return UpdateRecordedMetadataUseCase(
        repository=mock_repository,
        logger=mock_logger,
        base_dir=base_dir,
        video_editor=mock_video_editor,
        battle_history_service=mock_battle_history_service,
    )


@pytest.fixture
def battle_metadata():
    """バトルメタデータのサンプル。"""
    return RecordingMetadata(
        game_mode=GameMode.BATTLE,
        result=BattleResult(
            match=Match.ANARCHY_OPEN,
            rule=Rule.TURF_WAR,
            stage=Stage.SCORCH_GORGE,
            kill=10,
            death=5,
            special=3,
        ),
    )


@pytest.fixture
def salmon_metadata():
    """サーモンランメタデータのサンプル。"""
    return RecordingMetadata(
        game_mode=GameMode.SALMON,
        result=SalmonResult(
            hazard=100,
            stage=Stage.SCORCH_GORGE,
            golden_egg=50,
            power_egg=500,
            rescue=2,
            rescued=1,
        ),
    )


class TestUpdateRecordedMetadataHappyPath:
    """正常系のテスト。"""

    @pytest.mark.asyncio
    async def test_update_battle_metadata(
        self,
        use_case,
        base_dir,
        mock_repository,
        mock_battle_history_service,
        battle_metadata,
    ):
        """バトルメタデータを正常に更新できる。"""
        # テストファイルを作成
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        # リポジトリがアセットを返す設定
        asset = VideoAsset(video=video_path, metadata=battle_metadata)
        mock_repository.get_asset.return_value = asset

        # 更新内容
        patch = RecordingMetadataPatchDTO(
            kill=15,
            death=3,
            special=5,
        )

        # 実行
        result = await use_case.execute("recorded/test.mp4", patch)

        # メタデータが更新されて保存される
        mock_repository.save_edited_metadata.assert_called_once()
        saved_metadata: RecordingMetadata = (
            mock_repository.save_edited_metadata.call_args[0][1]
        )

        assert saved_metadata.result.kill == 15
        assert saved_metadata.result.death == 3
        assert saved_metadata.result.special == 5

        # BattleHistoryServiceと同期される
        mock_battle_history_service.sync_recording.assert_called_once()

        # DTOが返される
        assert isinstance(result, RecordedVideoDTO)

    @pytest.mark.asyncio
    async def test_update_with_empty_patch(
        self,
        use_case,
        base_dir,
        mock_repository,
        battle_metadata,
    ):
        """空の更新でも正常に処理される。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        asset = VideoAsset(video=video_path, metadata=battle_metadata)
        mock_repository.get_asset.return_value = asset

        # 空の更新
        patch = RecordingMetadataPatchDTO()

        _ = await use_case.execute("recorded/test.mp4", patch)

        # メタデータは変更されない
        mock_repository.save_edited_metadata.assert_called_once()
        saved_metadata: RecordingMetadata = (
            mock_repository.save_edited_metadata.call_args[0][1]
        )
        assert saved_metadata == battle_metadata


class TestUpdateRecordedMetadataValidation:
    """バリデーションのテスト。"""

    @pytest.mark.asyncio
    async def test_reject_update_on_non_battle_mode(
        self,
        use_case,
        base_dir,
        mock_repository,
        salmon_metadata,
    ):
        """サーモンランのメタデータをバトル項目で更新しようとするとエラー。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        asset = VideoAsset(video=video_path, metadata=salmon_metadata)
        mock_repository.get_asset.return_value = asset

        # バトルフィールドで更新を試みる
        patch = RecordingMetadataPatchDTO(
            kill=10,
            death=5,
        )

        with pytest.raises(
            ValueError, match="バトル以外のメタデータは更新できません"
        ):
            await use_case.execute("recorded/test.mp4", patch)

    @pytest.mark.asyncio
    async def test_reject_update_on_salmon_result(
        self,
        use_case,
        base_dir,
        mock_repository,
    ):
        """サーモンランの結果を持つメタデータは更新できない。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        # game_mode=BATTLEだがresult=SalmonResultの矛盾した状態
        metadata = RecordingMetadata(
            game_mode=GameMode.BATTLE,
            result=SalmonResult(
                hazard=100,
                stage=Stage.SCORCH_GORGE,
                golden_egg=50,
                power_egg=500,
                rescue=2,
                rescued=1,
            ),
        )
        asset = VideoAsset(video=video_path, metadata=metadata)
        mock_repository.get_asset.return_value = asset

        patch = RecordingMetadataPatchDTO(kill=10)

        with pytest.raises(
            ValueError, match="サーモンランのメタデータは更新できません"
        ):
            await use_case.execute("recorded/test.mp4", patch)


class TestUpdateRecordedMetadataErrorHandling:
    """エラーハンドリングのテスト。"""

    @pytest.mark.asyncio
    async def test_file_not_found(self, use_case, base_dir):
        """存在しないファイルを更新しようとするとFileNotFoundError。"""
        patch = RecordingMetadataPatchDTO(kill=10)

        with pytest.raises(
            FileNotFoundError, match="録画ファイルが見つかりません"
        ):
            await use_case.execute("recorded/nonexistent.mp4", patch)

    @pytest.mark.asyncio
    async def test_metadata_not_found(
        self, use_case, base_dir, mock_repository
    ):
        """メタデータが存在しない場合はFileNotFoundError。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        # メタデータなしのアセット
        mock_repository.get_asset.return_value = None

        patch = RecordingMetadataPatchDTO(kill=10)

        with pytest.raises(
            FileNotFoundError, match="メタデータが見つかりません"
        ):
            await use_case.execute("recorded/test.mp4", patch)


class TestUpdateRecordedMetadataIntegration:
    """統合動作のテスト。"""

    @pytest.mark.asyncio
    async def test_repository_and_history_sync(
        self,
        use_case,
        base_dir,
        mock_repository,
        mock_battle_history_service,
        battle_metadata,
    ):
        """リポジトリ保存とヒストリー同期が正しく連携する。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        asset = VideoAsset(video=video_path, metadata=battle_metadata)
        mock_repository.get_asset.return_value = asset

        patch = RecordingMetadataPatchDTO(kill=20)

        await use_case.execute("recorded/test.mp4", patch)

        # リポジトリとヒストリーサービスが呼ばれる
        assert mock_repository.save_edited_metadata.called
        assert mock_battle_history_service.sync_recording.called

        # 同じメタデータで呼ばれる
        saved_metadata = mock_repository.save_edited_metadata.call_args[0][1]
        synced_metadata = mock_battle_history_service.sync_recording.call_args[
            0
        ][1]
        assert saved_metadata == synced_metadata
