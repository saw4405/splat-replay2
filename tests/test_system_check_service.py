"""システムチェックサービスのテスト。"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from splat_replay.application.interfaces import (
    CommandExecutionError,
    CommandResult,
)
from splat_replay.application.services import SystemCheckService
from splat_replay.shared.logger import get_logger


class TestSystemCheckService:
    """SystemCheckServiceのテストクラス。"""

    def test_check_obs_installation_found(self, tmp_path: Path) -> None:
        """OBSが見つかった場合のテストを確認する。"""
        # モックのコマンドポートを作成
        mock_command_port = Mock()
        logger = get_logger()

        service = SystemCheckService(mock_command_port, logger)

        # OBSのインストール状態を確認（環境によって結果が異なる）
        result = service.check_obs_installation()

        # 結果が有効であることを確認（インストール済みまたは未インストール）
        assert isinstance(result.is_installed, bool)
        if not result.is_installed:
            assert result.error_message is not None

    def test_check_ffmpeg_installation_found(self) -> None:
        """FFMPEGが見つかった場合のテストを確認する。"""
        # モックのコマンドポートを作成
        mock_command_port = Mock()
        mock_command_port.check_command_exists.return_value = True
        mock_command_port.execute_command.return_value = CommandResult(
            return_code=0,
            stdout="ffmpeg version 4.4.2-0ubuntu0.22.04.1",
            stderr="",
        )

        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_ffmpeg_installation()

        assert result.is_installed is True
        assert result.version == "4.4.2-0ubuntu0.22.04.1"
        assert result.error_message is None

        # モックが正しく呼ばれたことを確認
        mock_command_port.check_command_exists.assert_called_once_with(
            "ffmpeg")
        mock_command_port.execute_command.assert_called_once()

    def test_check_ffmpeg_installation_not_found(self) -> None:
        """FFMPEGが見つからない場合のテストを確認する。"""
        # モックのコマンドポートを作成
        mock_command_port = Mock()
        mock_command_port.check_command_exists.return_value = False

        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_ffmpeg_installation()

        assert result.is_installed is False
        assert result.version is None
        assert result.error_message is not None

        # execute_commandは呼ばれないことを確認
        mock_command_port.execute_command.assert_not_called()

    def test_check_ffmpeg_installation_version_check_failed(self) -> None:
        """FFMPEGのバージョン確認が失敗した場合のテストを確認する。"""
        # モックのコマンドポートを作成
        mock_command_port = Mock()
        mock_command_port.check_command_exists.return_value = True
        mock_command_port.execute_command.return_value = CommandResult(
            return_code=1,
            stdout="",
            stderr="Error",
        )

        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_ffmpeg_installation()

        assert result.is_installed is False
        assert result.error_message is not None

    def test_check_ffmpeg_installation_command_error(self) -> None:
        """FFMPEGコマンド実行でエラーが発生した場合のテストを確認する。"""
        # モックのコマンドポートを作成
        mock_command_port = Mock()
        mock_command_port.check_command_exists.return_value = True
        mock_command_port.execute_command.side_effect = CommandExecutionError(
            "Command failed",
            ["ffmpeg", "-version"],
        )

        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_ffmpeg_installation()

        assert result.is_installed is False
        assert result.error_message is not None

    def test_check_tesseract_installation_found(self) -> None:
        """Tesseractが見つかった場合のテストを確認する。"""
        # モックのコマンドポートを作成
        mock_command_port = Mock()
        mock_command_port.check_command_exists.return_value = True
        mock_command_port.execute_command.return_value = CommandResult(
            return_code=0,
            stdout="tesseract 5.3.0",
            stderr="",
        )

        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_tesseract_installation()

        assert result.is_installed is True
        assert result.version == "5.3.0"
        assert result.error_message is None

    def test_check_tesseract_installation_not_found(self) -> None:
        """Tesseractが見つからない場合のテストを確認する。"""
        # モックのコマンドポートを作成
        mock_command_port = Mock()
        mock_command_port.check_command_exists.return_value = False

        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_tesseract_installation()

        assert result.is_installed is False
        assert result.version is None
        assert result.error_message is not None

    def test_check_environment_variable_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """環境変数が設定されている場合のテストを確認する。"""
        # 環境変数を設定
        monkeypatch.setenv("TEST_VAR", "test_value")

        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_environment_variable("TEST_VAR")

        assert result is True

    def test_check_environment_variable_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """環境変数が設定されていない場合のテストを確認する。"""
        # 環境変数を削除
        monkeypatch.delenv("TEST_VAR", raising=False)

        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_environment_variable("TEST_VAR")

        assert result is False

    def test_check_environment_variable_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """環境変数が空文字列の場合のテストを確認する。"""
        # 環境変数を空文字列に設定
        monkeypatch.setenv("TEST_VAR", "")

        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_environment_variable("TEST_VAR")

        assert result is False

    def test_check_file_exists_true(self, tmp_path: Path) -> None:
        """ファイルが存在する場合のテストを確認する。"""
        # テスト用のファイルを作成
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_file_exists(test_file)

        assert result is True

    def test_check_file_exists_false(self, tmp_path: Path) -> None:
        """ファイルが存在しない場合のテストを確認する。"""
        # 存在しないファイルパス
        test_file = tmp_path / "nonexistent.txt"

        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_file_exists(test_file)

        assert result is False

    def test_check_file_exists_directory(self, tmp_path: Path) -> None:
        """ディレクトリの場合はFalseを返すことを確認する。"""
        # テスト用のディレクトリを作成
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        result = service.check_file_exists(test_dir)

        assert result is False

    def test_extract_ffmpeg_version(self) -> None:
        """FFMPEGバージョン抽出が正しく動作することを確認する。"""
        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        output = "ffmpeg version 4.4.2-0ubuntu0.22.04.1 Copyright (c) 2000-2021"
        version = service._extract_ffmpeg_version(output)

        assert version == "4.4.2-0ubuntu0.22.04.1"

    def test_extract_ffmpeg_version_not_found(self) -> None:
        """FFMPEGバージョンが見つからない場合にNoneを返すことを確認する。"""
        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        output = "Invalid output"
        version = service._extract_ffmpeg_version(output)

        assert version is None

    def test_extract_tesseract_version(self) -> None:
        """Tesseractバージョン抽出が正しく動作することを確認する。"""
        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        output = "tesseract 5.3.0\n leptonica-1.82.0"
        version = service._extract_tesseract_version(output)

        assert version == "5.3.0"

    def test_extract_tesseract_version_not_found(self) -> None:
        """Tesseractバージョンが見つからない場合にNoneを返すことを確認する。"""
        mock_command_port = Mock()
        logger = get_logger()
        service = SystemCheckService(mock_command_port, logger)

        output = "Invalid output"
        version = service._extract_tesseract_version(output)

        assert version is None
