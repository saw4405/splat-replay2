"""エラーハンドラーのテスト。"""

from splat_replay.application.services import (
    ErrorHandler,
    FileOperationError,
    InstallerError,
    InstallationStateError,
    NetworkError,
    SystemCheckError,
    UserCancelledError,
)
from splat_replay.shared.logger import get_logger


class TestErrorHandler:
    """ErrorHandlerのテストクラス。"""

    def test_handle_installer_error(self) -> None:
        """インストーラーエラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = InstallerError(
            message="Test error",
            error_code="TEST_ERROR",
            recovery_action="Test recovery",
        )

        response = handler.handle_error(error)

        assert response.error_code == "TEST_ERROR"
        assert response.message == "Test error"
        assert response.is_recoverable
        assert "Test recovery" in response.recovery_actions

    def test_handle_system_check_error(self) -> None:
        """システムチェックエラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = SystemCheckError(
            message="FFMPEG not found",
            software_name="FFMPEG",
        )

        response = handler.handle_error(error)

        assert response.error_code == "SYSTEM_CHECK_FFMPEG"
        assert "FFMPEG" in response.user_message
        assert response.is_recoverable
        assert len(response.recovery_actions) > 0

    def test_handle_file_operation_error(self) -> None:
        """ファイル操作エラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = FileOperationError(
            message="Cannot write file",
            file_path="/path/to/file",
        )

        response = handler.handle_error(error)

        assert response.error_code == "FILE_OPERATION"
        assert "ファイル操作" in response.user_message
        assert response.is_recoverable
        assert any("アクセス権限" in action for action in response.recovery_actions)

    def test_handle_network_error(self) -> None:
        """ネットワークエラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = NetworkError(
            message="Connection failed",
            url="https://example.com",
        )

        response = handler.handle_error(error)

        assert response.error_code == "NETWORK"
        assert "ネットワーク" in response.user_message
        assert response.is_recoverable
        assert any("インターネット接続" in action for action in response.recovery_actions)

    def test_handle_installation_state_error(self) -> None:
        """インストール状態エラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = InstallationStateError(
            message="Invalid state",
        )

        response = handler.handle_error(error)

        assert response.error_code == "INSTALLATION_STATE"
        assert "インストール状態" in response.user_message
        assert response.is_recoverable

    def test_handle_user_cancelled_error(self) -> None:
        """ユーザーキャンセルエラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = UserCancelledError()

        response = handler.handle_error(error)

        assert response.error_code == "USER_CANCELLED"
        assert not response.is_recoverable
        assert any("再起動" in action for action in response.recovery_actions)

    def test_handle_generic_error(self) -> None:
        """一般的なエラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = ValueError("Generic error")

        response = handler.handle_error(error)

        assert response.error_code == "UNKNOWN"
        assert "予期しない" in response.user_message
        assert response.is_recoverable

    def test_suggest_recovery_action_with_custom_action(self) -> None:
        """カスタム回復アクションが提案されることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = InstallerError(
            message="Test error",
            error_code="TEST",
            recovery_action="Custom recovery action",
        )

        actions = handler.suggest_recovery_action(error)

        assert "Custom recovery action" in actions

    def test_suggest_recovery_action_system_check(self) -> None:
        """システムチェックエラーの回復アクションが提案されることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = SystemCheckError(
            message="Software not found",
            software_name="TestSoftware",
        )

        actions = handler.suggest_recovery_action(error)

        assert any("TestSoftware" in action for action in actions)
        assert any("環境変数" in action for action in actions)

    def test_log_error_with_context(self) -> None:
        """コンテキスト付きでエラーをログに記録できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = InstallerError(
            message="Test error",
            error_code="TEST",
        )
        context = {"step": "hardware_check", "user": "test_user"}

        # ログ記録が例外を投げないことを確認
        handler.log_error(error, context)

    def test_error_with_cause(self) -> None:
        """原因となった例外を持つエラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        cause = ValueError("Original error")
        error = InstallerError(
            message="Wrapper error",
            error_code="WRAPPER",
            cause=cause,
        )

        response = handler.handle_error(error)

        assert response.error_code == "WRAPPER"
        assert response.message == "Wrapper error"

    def test_file_operation_error_with_path(self) -> None:
        """ファイルパス付きのファイル操作エラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = FileOperationError(
            message="Cannot access file",
            file_path="/test/path/file.txt",
        )

        actions = handler.suggest_recovery_action(error)

        assert any("/test/path/file.txt" in action for action in actions)

    def test_network_error_with_url(self) -> None:
        """URL付きのネットワークエラーを処理できることをテストする。"""
        logger = get_logger()
        handler = ErrorHandler(logger)

        error = NetworkError(
            message="Connection timeout",
            url="https://api.example.com",
        )

        actions = handler.suggest_recovery_action(error)

        assert any("https://api.example.com" in action for action in actions)
