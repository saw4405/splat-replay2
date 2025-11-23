"""システムコマンドアダプターのテスト。"""

import sys

import pytest

from splat_replay.application.interfaces import CommandExecutionError
from splat_replay.infrastructure.adapters import SystemCommandAdapter
from splat_replay.shared.logger import get_logger


class TestSystemCommandAdapter:
    """SystemCommandAdapterのテストクラス。"""

    def test_execute_command_success(self) -> None:
        """コマンド実行が成功する場合のテストを確認する。"""
        logger = get_logger()
        adapter = SystemCommandAdapter(logger)

        # Pythonのバージョン確認コマンドを実行
        result = adapter.execute_command(
            [sys.executable, "--version"],
            timeout=5.0,
        )

        assert result.success
        assert result.return_code == 0
        assert "Python" in result.stdout or "Python" in result.stderr

    def test_execute_command_failure(self) -> None:
        """コマンド実行が失敗する場合のテストを確認する。"""
        logger = get_logger()
        adapter = SystemCommandAdapter(logger)

        # 存在しないオプションを指定してエラーを発生させる
        result = adapter.execute_command(
            [sys.executable, "--invalid-option"],
            timeout=5.0,
        )

        assert not result.success
        assert result.return_code != 0

    def test_execute_command_timeout(self) -> None:
        """コマンドがタイムアウトする場合のテストを確認する。"""
        logger = get_logger()
        adapter = SystemCommandAdapter(logger)

        # 長時間実行されるコマンドでタイムアウトをテスト
        # Windowsではpingコマンド、Unix系ではsleepコマンドを使用
        if sys.platform == "win32":
            # ping -n 10でタイムアウトをテスト
            command = ["ping", "-n", "10", "127.0.0.1"]
        else:
            command = ["sleep", "10"]

        with pytest.raises(CommandExecutionError) as exc_info:
            adapter.execute_command(command, timeout=0.5)

        assert "timed out" in str(exc_info.value).lower()

    def test_execute_command_not_found(self) -> None:
        """存在しないコマンドを実行した場合のテストを確認する。"""
        logger = get_logger()
        adapter = SystemCommandAdapter(logger)

        with pytest.raises(CommandExecutionError) as exc_info:
            adapter.execute_command(
                ["nonexistent_command_12345"],
                timeout=5.0,
            )

        assert "not found" in str(exc_info.value).lower()

    def test_execute_command_empty_list(self) -> None:
        """空のコマンドリストを渡した場合のテストを確認する。"""
        logger = get_logger()
        adapter = SystemCommandAdapter(logger)

        with pytest.raises(CommandExecutionError) as exc_info:
            adapter.execute_command([], timeout=5.0)

        assert "empty" in str(exc_info.value).lower()

    def test_check_command_exists_true(self) -> None:
        """存在するコマンドの確認テストを確認する。"""
        logger = get_logger()
        adapter = SystemCommandAdapter(logger)

        # Pythonコマンドは確実に存在する
        result = adapter.check_command_exists("python")

        assert result is True

    def test_check_command_exists_false(self) -> None:
        """存在しないコマンドの確認テストを確認する。"""
        logger = get_logger()
        adapter = SystemCommandAdapter(logger)

        result = adapter.check_command_exists("nonexistent_command_12345")

        assert result is False

    def test_command_injection_prevention(self) -> None:
        """コマンドインジェクション対策が機能することを確認する。"""
        logger = get_logger()
        adapter = SystemCommandAdapter(logger)

        # シェルメタ文字を含むコマンドを実行
        # shell=Falseなので、これらは単なる引数として扱われる
        result = adapter.execute_command(
            [sys.executable, "--version", "&&", "echo", "injected"],
            timeout=5.0,
        )

        # Pythonは追加の引数を無視して正常に実行される
        # 重要なのは"injected"という文字列が出力されないこと
        assert "injected" not in result.stdout.lower()
        assert "injected" not in result.stderr.lower()
