"""インストーラーサービスのテスト。"""

import tempfile
from pathlib import Path

import pytest

from splat_replay.application.services import InstallerService
from splat_replay.domain.models import InstallationStep
from splat_replay.infrastructure.adapters import InstallationStateFileAdapter
from splat_replay.shared.logger import get_logger


class TestInstallerService:
    """InstallerServiceのテストクラス。"""

    def test_check_installation_status_default(self, tmp_path: Path) -> None:
        """デフォルトのインストール状態を確認できることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        state = service.check_installation_status()

        assert not state.is_completed
        assert state.current_step == InstallationStep.HARDWARE_CHECK
        assert state.completed_steps == []
        assert state.skipped_steps == []

    def test_start_installation(self, tmp_path: Path) -> None:
        """インストーラーを開始できることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        state = service.start_installation()

        assert not state.is_completed
        assert state.current_step == InstallationStep.HARDWARE_CHECK
        assert file_path.exists()

    def test_complete_installation(self, tmp_path: Path) -> None:
        """インストールを完了できることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        state = service.complete_installation()

        assert state.is_completed
        assert state.installation_date is not None

    def test_get_current_step(self, tmp_path: Path) -> None:
        """現在のステップを取得できることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        current_step = service.get_current_step()

        assert current_step == InstallationStep.HARDWARE_CHECK

    def test_proceed_to_next_step_success(self, tmp_path: Path) -> None:
        """次のステップに進めることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        service.mark_step_completed(InstallationStep.HARDWARE_CHECK)

        state = service.proceed_to_next_step()

        assert state.current_step == InstallationStep.OBS_SETUP
        assert InstallationStep.HARDWARE_CHECK in state.completed_steps

    def test_proceed_to_next_step_failure_not_completed(self, tmp_path: Path) -> None:
        """ステップが完了していない場合に次に進めないことをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()

        with pytest.raises(ValueError) as exc_info:
            service.proceed_to_next_step()

        assert "cannot proceed" in str(exc_info.value).lower()

    def test_proceed_to_next_step_completes_installation(self, tmp_path: Path) -> None:
        """最後のステップで次に進むとインストールが完了することをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        # 全ステップを完了させる
        service.start_installation()
        for step in InstallationStep.get_all_steps():
            service.mark_step_completed(step)
            if step != InstallationStep.YOUTUBE_SETUP:
                service.proceed_to_next_step()

        # 最後のステップで次に進む
        state = service.proceed_to_next_step()

        assert state.is_completed
        assert state.installation_date is not None

    def test_go_back_to_previous_step_success(self, tmp_path: Path) -> None:
        """前のステップに戻れることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        service.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        service.proceed_to_next_step()

        state = service.go_back_to_previous_step()

        assert state.current_step == InstallationStep.HARDWARE_CHECK

    def test_go_back_to_previous_step_failure_at_first(self, tmp_path: Path) -> None:
        """最初のステップで前に戻れないことをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()

        with pytest.raises(ValueError) as exc_info:
            service.go_back_to_previous_step()

        assert "cannot go back" in str(exc_info.value).lower()

    def test_skip_current_step(self, tmp_path: Path) -> None:
        """現在のステップをスキップできることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        state = service.skip_current_step()

        assert InstallationStep.HARDWARE_CHECK in state.skipped_steps
        assert InstallationStep.HARDWARE_CHECK not in state.completed_steps

    def test_mark_step_completed(self, tmp_path: Path) -> None:
        """ステップを完了済みとしてマークできることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        state = service.mark_step_completed(InstallationStep.HARDWARE_CHECK)

        assert InstallationStep.HARDWARE_CHECK in state.completed_steps
        assert InstallationStep.HARDWARE_CHECK not in state.skipped_steps

    def test_is_installation_completed(self, tmp_path: Path) -> None:
        """インストール完了状態を確認できることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        assert not service.is_installation_completed()

        service.complete_installation()
        assert service.is_installation_completed()

    def test_get_progress_percentage(self, tmp_path: Path) -> None:
        """進行状況のパーセンテージを取得できることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        assert service.get_progress_percentage() == 0.0

        service.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        progress = service.get_progress_percentage()
        expected = (1 / 6) * 100
        assert abs(progress - expected) < 0.01

    def test_get_remaining_steps(self, tmp_path: Path) -> None:
        """残りのステップを取得できることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        remaining = service.get_remaining_steps()
        assert len(remaining) == 6

        service.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        remaining = service.get_remaining_steps()
        assert len(remaining) == 5
        assert InstallationStep.HARDWARE_CHECK not in remaining

    def test_reset_installation(self, tmp_path: Path) -> None:
        """インストール状態をリセットできることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        # いくつかのステップを完了させる
        service.start_installation()
        service.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        service.proceed_to_next_step()
        service.mark_step_completed(InstallationStep.OBS_SETUP)

        # リセット
        state = service.reset_installation()

        assert not state.is_completed
        assert state.current_step == InstallationStep.HARDWARE_CHECK
        assert state.completed_steps == []
        assert state.skipped_steps == []

    def test_skip_and_proceed(self, tmp_path: Path) -> None:
        """ステップをスキップして次に進めることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()
        service = InstallerService(repository, logger)

        service.start_installation()
        service.skip_current_step()
        state = service.proceed_to_next_step()

        assert state.current_step == InstallationStep.OBS_SETUP
        assert InstallationStep.HARDWARE_CHECK in state.skipped_steps

    def test_state_persistence(self, tmp_path: Path) -> None:
        """状態が永続化されることをテストする。"""
        file_path = tmp_path / "installer.toml"
        repository = InstallationStateFileAdapter(file_path)
        logger = get_logger()

        # 最初のサービスインスタンスで状態を変更
        service1 = InstallerService(repository, logger)
        service1.start_installation()
        service1.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        service1.proceed_to_next_step()

        # 新しいサービスインスタンスで状態を読み込み
        service2 = InstallerService(repository, logger)
        state = service2.check_installation_status()

        assert state.current_step == InstallationStep.OBS_SETUP
        assert InstallationStep.HARDWARE_CHECK in state.completed_steps
