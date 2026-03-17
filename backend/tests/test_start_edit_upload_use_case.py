"""StartEditUploadUseCase のテスト。

責務：
- 編集・アップロード開始フローの検証
- バックグラウンドタスク管理
- 状態管理
- 重複起動防止

分類: logic
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from splat_replay.application.use_cases.assets.start_edit_upload import (
    StartEditUploadUseCase,
)


@pytest.fixture
def mock_editor():
    """AutoEditorのモック。"""
    return AsyncMock()


@pytest.fixture
def mock_uploader():
    """AutoUploaderのモック。"""
    return AsyncMock()


@pytest.fixture
def mock_event_bus():
    """EventBusPortのモック。"""
    return MagicMock()


@pytest.fixture
def mock_config():
    """ConfigPortのモック。"""
    return MagicMock()


@pytest.fixture
def mock_logger():
    """LoggerPortのモック。"""
    return MagicMock()


@pytest.fixture
def use_case(
    mock_editor, mock_uploader, mock_event_bus, mock_config, mock_logger
):
    """StartEditUploadUseCaseのインスタンス。"""
    return StartEditUploadUseCase(
        editor=mock_editor,
        uploader=mock_uploader,
        event_bus=mock_event_bus,
        config=mock_config,
        logger=mock_logger,
    )


class TestStartEditUploadHappyPath:
    """正常系のテスト。"""

    @pytest.mark.asyncio
    async def test_execute_starts_background_task(
        self, use_case, mock_editor, mock_uploader, mock_logger
    ):
        """execute()を呼ぶとバックグラウンドタスクが開始される。"""
        await use_case.execute()

        # 状態が running になる
        assert use_case.get_state() == "running"
        assert use_case.is_running()

        # 開始ログが記録される
        mock_logger.info.assert_called()

        # タスク完了を待機
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_manual_trigger(self, use_case):
        """manual トリガーで起動できる。"""
        await use_case.execute(trigger="manual")

        assert use_case.is_running()

    @pytest.mark.asyncio
    async def test_auto_trigger(self, use_case):
        """auto トリガーで起動できる。"""
        await use_case.execute(trigger="auto")

        assert use_case.is_running()


class TestStartEditUploadStateManagement:
    """状態管理のテスト。"""

    @pytest.mark.asyncio
    async def test_initial_state_is_idle(self, use_case):
        """初期状態は idle。"""
        assert use_case.get_state() == "idle"
        assert not use_case.is_running()

    @pytest.mark.asyncio
    async def test_state_transition_to_running(self, use_case):
        """execute()で状態が running に遷移する。"""
        await use_case.execute()

        assert use_case.get_state() == "running"

    @pytest.mark.asyncio
    async def test_state_transition_to_succeeded(
        self, use_case, mock_editor, mock_uploader
    ):
        """正常完了時は succeeded に遷移する。"""
        await use_case.execute()

        # タスク完了を待機
        await asyncio.sleep(0.1)

        assert use_case.get_state() == "succeeded"
        assert not use_case.is_running()

    @pytest.mark.asyncio
    async def test_state_transition_to_failed(
        self, use_case, mock_editor, mock_uploader
    ):
        """エラー発生時は failed に遷移する。"""
        mock_editor.execute.side_effect = RuntimeError("編集エラー")

        await use_case.execute()

        # タスク完了を待機
        await asyncio.sleep(0.1)

        assert use_case.get_state() == "failed"
        assert not use_case.is_running()


class TestStartEditUploadDuplicatePrevention:
    """重複起動防止のテスト。"""

    @pytest.mark.asyncio
    async def test_reject_duplicate_start(self, use_case):
        """実行中に再度 execute() を呼ぶとエラー。"""
        await use_case.execute()

        # 実行中なので2回目はエラー
        with pytest.raises(RuntimeError, match="既に実行中"):
            await use_case.execute()

    @pytest.mark.asyncio
    async def test_allow_restart_after_completion(
        self, use_case, mock_editor, mock_uploader
    ):
        """完了後は再度 execute() できる。"""
        # 1回目
        await use_case.execute()
        await asyncio.sleep(0.1)  # 完了を待機

        # 2回目（エラーにならない）
        await use_case.execute()

        assert use_case.is_running()


class TestStartEditUploadTaskExecution:
    """タスク実行のテスト。"""

    @pytest.mark.asyncio
    async def test_editor_and_uploader_called_in_order(
        self, use_case, mock_editor, mock_uploader
    ):
        """編集→アップロードの順で呼ばれる。"""
        call_order = []

        async def track_editor():
            call_order.append("editor")

        async def track_uploader():
            call_order.append("uploader")

        mock_editor.execute.side_effect = track_editor
        mock_uploader.execute.side_effect = track_uploader

        await use_case.execute()
        await asyncio.sleep(0.1)

        assert call_order == ["editor", "uploader"]

    @pytest.mark.asyncio
    async def test_editor_failure_stops_uploader(
        self, use_case, mock_editor, mock_uploader
    ):
        """編集失敗時はアップロードが実行されない。"""
        mock_editor.execute.side_effect = RuntimeError("編集失敗")

        await use_case.execute()
        await asyncio.sleep(0.1)

        # 編集は試行される
        mock_editor.execute.assert_awaited_once()

        # アップロードは実行されない
        mock_uploader.execute.assert_not_awaited()


class TestStartEditUploadEventPublishing:
    """イベント発行のテスト。"""

    @pytest.mark.asyncio
    async def test_publish_success_event(self, use_case, mock_event_bus):
        """成功時はEditUploadCompletedイベントが発行される。"""
        await use_case.execute()
        await asyncio.sleep(0.1)

        # イベントが発行される
        mock_event_bus.publish_domain_event.assert_called()

        # EditUploadCompletedイベントを探す
        from splat_replay.domain.events import EditUploadCompleted

        events = [
            call[0][0]
            for call in mock_event_bus.publish_domain_event.call_args_list
        ]
        completed_events = [
            e for e in events if isinstance(e, EditUploadCompleted)
        ]
        assert len(completed_events) > 0, (
            "EditUploadCompletedイベントが発行されていません"
        )
        event = completed_events[0]
        assert event.success is True

    @pytest.mark.asyncio
    async def test_publish_failure_event(
        self, use_case, mock_editor, mock_event_bus
    ):
        """失敗時はErrorイベントが発行される。"""
        mock_editor.execute.side_effect = RuntimeError("編集失敗")

        await use_case.execute()
        await asyncio.sleep(0.1)

        # イベントが発行される
        mock_event_bus.publish_domain_event.assert_called()

        # EditUploadCompletedイベントを探す
        from splat_replay.domain.events import EditUploadCompleted

        events = [
            call[0][0]
            for call in mock_event_bus.publish_domain_event.call_args_list
        ]
        completed_events = [
            e for e in events if isinstance(e, EditUploadCompleted)
        ]
        assert len(completed_events) > 0, (
            "EditUploadCompletedイベントが発行されていません"
        )
        event = completed_events[0]
        assert event.success is False


class TestStartEditUploadMessageHandling:
    """メッセージ管理のテスト。"""

    @pytest.mark.asyncio
    async def test_message_on_start(self, use_case):
        """開始時にメッセージが設定される。"""
        await use_case.execute()

        message = use_case.get_message()
        assert "開始" in message

    @pytest.mark.asyncio
    async def test_message_on_success(self, use_case):
        """成功時にメッセージが更新される。"""
        await use_case.execute()
        await asyncio.sleep(0.1)

        message = use_case.get_message()
        assert "完了" in message

    @pytest.mark.asyncio
    async def test_message_on_failure(self, use_case, mock_editor):
        """失敗時にエラーメッセージが設定される。"""
        mock_editor.execute.side_effect = RuntimeError("テストエラー")

        await use_case.execute()
        await asyncio.sleep(0.1)

        message = use_case.get_message()
        assert "失敗" in message
        assert "テストエラー" in message
