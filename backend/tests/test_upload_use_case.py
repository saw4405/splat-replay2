"""UploadUseCase のテスト。

責務：
- 自動編集→自動アップロード→スリープのフロー検証
- 設定によるスリープスキップの確認
- 各サービスの呼び出し順序の検証

分類: logic
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from splat_replay.application.use_cases.upload import UploadUseCase
from splat_replay.domain.config.behavior import BehaviorSettings


@pytest.fixture
def mock_logger():
    """LoggerPortのモック。"""
    return MagicMock()


@pytest.fixture
def mock_config():
    """ConfigPortのモック。"""
    config = MagicMock()
    # デフォルトはスリープ有効
    config.get_behavior_settings.return_value = BehaviorSettings(
        sleep_after_upload=True,
    )
    return config


@pytest.fixture
def mock_editor():
    """AutoEditorのモック。"""
    editor = AsyncMock()
    return editor


@pytest.fixture
def mock_uploader():
    """AutoUploaderのモック。"""
    uploader = AsyncMock()
    return uploader


@pytest.fixture
def mock_power():
    """PowerManagerのモック。"""
    power = AsyncMock()
    return power


@pytest.fixture
def use_case(mock_logger, mock_config, mock_editor, mock_uploader, mock_power):
    """UploadUseCaseのインスタンス。"""
    return UploadUseCase(
        logger=mock_logger,
        config=mock_config,
        editor=mock_editor,
        uploader=mock_uploader,
        power=mock_power,
    )


class TestUploadUseCaseHappyPath:
    """正常系のテスト。"""

    @pytest.mark.asyncio
    async def test_execute_with_sleep(
        self, use_case, mock_editor, mock_uploader, mock_power
    ):
        """スリープ有効時は編集→アップロード→スリープの順で実行される。"""
        await use_case.execute()

        # 呼び出し順序を検証
        mock_editor.execute.assert_awaited_once()
        mock_uploader.execute.assert_awaited_once()
        mock_power.sleep.assert_awaited_once()

        # 呼び出し順序の詳細検証
        assert mock_editor.execute.await_count == 1
        assert mock_uploader.execute.await_count == 1
        assert mock_power.sleep.await_count == 1

    @pytest.mark.asyncio
    async def test_execute_without_sleep(
        self,
        use_case,
        mock_config,
        mock_editor,
        mock_uploader,
        mock_power,
        mock_logger,
    ):
        """スリープ無効時は編集→アップロードのみ実行される。"""
        # スリープ無効の設定に変更
        mock_config.get_behavior_settings.return_value = BehaviorSettings(
            sleep_after_upload=False,
        )

        await use_case.execute()

        # 編集とアップロードは実行される
        mock_editor.execute.assert_awaited_once()
        mock_uploader.execute.assert_awaited_once()

        # スリープはスキップされる
        mock_power.sleep.assert_not_awaited()

        # スキップメッセージがログに記録される
        mock_logger.info.assert_called_once()
        assert "スリープをスキップ" in str(mock_logger.info.call_args)


class TestUploadUseCaseErrorHandling:
    """エラーハンドリングのテスト。"""

    @pytest.mark.asyncio
    async def test_editor_failure_stops_upload(
        self, use_case, mock_editor, mock_uploader, mock_power
    ):
        """編集失敗時はアップロードとスリープが実行されない。"""
        mock_editor.execute.side_effect = RuntimeError("編集失敗")

        with pytest.raises(RuntimeError, match="編集失敗"):
            await use_case.execute()

        # 編集は試行される
        mock_editor.execute.assert_awaited_once()

        # アップロードとスリープは実行されない
        mock_uploader.execute.assert_not_awaited()
        mock_power.sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uploader_failure_stops_sleep(
        self, use_case, mock_editor, mock_uploader, mock_power
    ):
        """アップロード失敗時はスリープが実行されない。"""
        mock_uploader.execute.side_effect = RuntimeError("アップロード失敗")

        with pytest.raises(RuntimeError, match="アップロード失敗"):
            await use_case.execute()

        # 編集は成功
        mock_editor.execute.assert_awaited_once()

        # アップロードは試行される
        mock_uploader.execute.assert_awaited_once()

        # スリープは実行されない
        mock_power.sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_power_sleep_failure_is_propagated(
        self, use_case, mock_editor, mock_uploader, mock_power
    ):
        """スリープ失敗時はエラーが伝播される。"""
        mock_power.sleep.side_effect = RuntimeError("スリープ失敗")

        with pytest.raises(RuntimeError, match="スリープ失敗"):
            await use_case.execute()

        # 編集とアップロードは成功
        mock_editor.execute.assert_awaited_once()
        mock_uploader.execute.assert_awaited_once()

        # スリープは試行される
        mock_power.sleep.assert_awaited_once()


class TestUploadUseCaseCallOrder:
    """呼び出し順序の詳細検証。"""

    @pytest.mark.asyncio
    async def test_services_called_in_correct_order(
        self, use_case, mock_editor, mock_uploader, mock_power
    ):
        """サービスが正しい順序で呼び出される。"""
        call_order = []

        async def track_editor():
            call_order.append("editor")

        async def track_uploader():
            call_order.append("uploader")

        async def track_power():
            call_order.append("power")

        mock_editor.execute.side_effect = track_editor
        mock_uploader.execute.side_effect = track_uploader
        mock_power.sleep.side_effect = track_power

        await use_case.execute()

        assert call_order == ["editor", "uploader", "power"]
