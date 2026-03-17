"""DeleteRecordedVideoUseCase のテスト。

責務：
- 録画ファイル削除フローの検証
- ファイル存在確認
- リポジトリ連携
- エラーハンドリング

分類: logic
"""

from unittest.mock import MagicMock

import pytest

from splat_replay.application.use_cases.assets.delete_recorded_video import (
    DeleteRecordedVideoUseCase,
)


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
def use_case(mock_repository, mock_logger, base_dir):
    """DeleteRecordedVideoUseCaseのインスタンス。"""
    return DeleteRecordedVideoUseCase(
        repository=mock_repository,
        logger=mock_logger,
        base_dir=base_dir,
    )


class TestDeleteRecordedVideoHappyPath:
    """正常系のテスト。"""

    @pytest.mark.asyncio
    async def test_delete_existing_video(
        self, use_case, base_dir, mock_repository, mock_logger
    ):
        """存在するビデオを正常に削除できる。"""
        # テストファイルを作成
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        # リポジトリが削除成功を返す
        mock_repository.delete_recording.return_value = True

        # 実行
        await use_case.execute("recorded/test.mp4")

        # リポジトリの削除メソッドが呼ばれる
        mock_repository.delete_recording.assert_called_once_with(video_path)

        # 成功ログが記録される
        mock_logger.info.assert_called_once()
        assert "削除しました" in str(mock_logger.info.call_args)

    @pytest.mark.asyncio
    async def test_repository_called_with_correct_path(
        self, use_case, base_dir, mock_repository
    ):
        """リポジトリに正しいパスが渡される。"""
        video_path = base_dir / "recorded" / "subdir" / "video.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        mock_repository.delete_recording.return_value = True

        await use_case.execute("recorded/subdir/video.mp4")

        # 絶対パスで呼ばれる
        called_path = mock_repository.delete_recording.call_args[0][0]
        assert called_path == video_path
        assert called_path.is_absolute()


class TestDeleteRecordedVideoErrorHandling:
    """エラーハンドリングのテスト。"""

    @pytest.mark.asyncio
    async def test_file_not_found(
        self, use_case, mock_repository, mock_logger
    ):
        """存在しないファイルを削除しようとするとFileNotFoundError。"""
        with pytest.raises(
            FileNotFoundError, match="録画ファイルが見つかりません"
        ):
            await use_case.execute("recorded/nonexistent.mp4")

        # リポジトリは呼ばれない
        mock_repository.delete_recording.assert_not_called()

        # 警告ログが記録される
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_repository_delete_failure(
        self, use_case, base_dir, mock_repository, mock_logger
    ):
        """リポジトリの削除が失敗した場合はRuntimeError。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        # リポジトリが削除失敗を返す
        mock_repository.delete_recording.return_value = False

        with pytest.raises(RuntimeError, match="削除に失敗しました"):
            await use_case.execute("recorded/test.mp4")

        # エラーログが記録される
        mock_logger.error.assert_called_once()
        assert "削除に失敗" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_repository_exception_propagates(
        self, use_case, base_dir, mock_repository
    ):
        """リポジトリで例外が発生した場合は伝播される。"""
        video_path = base_dir / "recorded" / "test.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        # リポジトリで例外発生
        mock_repository.delete_recording.side_effect = PermissionError(
            "Permission denied"
        )

        with pytest.raises(PermissionError, match="Permission denied"):
            await use_case.execute("recorded/test.mp4")


class TestDeleteRecordedVideoEdgeCases:
    """境界条件のテスト。"""

    @pytest.mark.asyncio
    async def test_delete_with_special_characters_in_path(
        self, use_case, base_dir, mock_repository
    ):
        """パスに特殊文字が含まれる場合も正常に処理される。"""
        video_path = base_dir / "recorded" / "動画 (1).mp4"
        video_path.parent.mkdir(parents=True)
        video_path.touch()

        mock_repository.delete_recording.return_value = True

        await use_case.execute("recorded/動画 (1).mp4")

        mock_repository.delete_recording.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_with_deep_nested_path(
        self, use_case, base_dir, mock_repository
    ):
        """深くネストされたパスでも正常に処理される。"""
        video_path = base_dir / "recorded" / "a" / "b" / "c" / "d" / "test.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.touch()

        mock_repository.delete_recording.return_value = True

        await use_case.execute("recorded/a/b/c/d/test.mp4")

        mock_repository.delete_recording.assert_called_once()
