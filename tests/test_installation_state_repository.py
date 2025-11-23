"""インストール状態リポジトリのテスト。"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from splat_replay.domain.models import InstallationState, InstallationStep
from splat_replay.domain.repositories import RepositoryError
from splat_replay.infrastructure.adapters import InstallationStateFileAdapter


class TestInstallationStateFileAdapter:
    """InstallationStateFileAdapterのテストクラス。"""

    def test_save_and_load_installation_state(self) -> None:
        """インストール状態の保存と読み込みが正しく動作することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # テスト用の状態を作成
            state = InstallationState()
            state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
            state.mark_step_skipped(InstallationStep.OBS_SETUP)
            state.current_step = InstallationStep.FFMPEG_SETUP

            # 保存
            adapter.save_installation_state(state)

            # ファイルが作成されることを確認
            assert file_path.exists()

            # 読み込み
            loaded_state = adapter.load_installation_state()

            # 状態が正しく復元されることを確認
            assert loaded_state.is_completed == state.is_completed
            assert loaded_state.current_step == state.current_step
            assert loaded_state.completed_steps == state.completed_steps
            assert loaded_state.skipped_steps == state.skipped_steps

    def test_load_installation_state_returns_default_when_file_not_exists(self) -> None:
        """ファイルが存在しない場合にデフォルト状態が返されることを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "nonexistent.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # ファイルが存在しないことを確認
            assert not file_path.exists()

            # 読み込み
            state = adapter.load_installation_state()

            # デフォルト状態が返されることを確認
            assert not state.is_completed
            assert state.current_step == InstallationStep.HARDWARE_CHECK
            assert state.completed_steps == []
            assert state.skipped_steps == []
            assert state.installation_date is None

    def test_save_installation_state_creates_directory(self) -> None:
        """保存時にディレクトリが存在しない場合に作成されることを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "subdir" / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # ディレクトリが存在しないことを確認
            assert not file_path.parent.exists()

            # 状態を保存
            state = InstallationState()
            adapter.save_installation_state(state)

            # ディレクトリとファイルが作成されることを確認
            assert file_path.parent.exists()
            assert file_path.exists()

    def test_mark_step_completed_updates_and_saves_state(self) -> None:
        """ステップ完了マークが状態を更新して保存することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # 初期状態を保存
            initial_state = InstallationState()
            adapter.save_installation_state(initial_state)

            # ステップを完了済みとしてマーク
            adapter.mark_step_completed(InstallationStep.HARDWARE_CHECK)

            # 状態を読み込んで確認
            updated_state = adapter.load_installation_state()
            assert InstallationStep.HARDWARE_CHECK in updated_state.completed_steps

    def test_is_installation_completed_returns_correct_status(self) -> None:
        """インストール完了状態の確認が正しく動作することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # 初期状態では未完了
            assert not adapter.is_installation_completed()

            # 完了状態を保存
            completed_state = InstallationState()
            completed_state.complete_installation()
            adapter.save_installation_state(completed_state)

            # 完了状態が確認できることを確認
            assert adapter.is_installation_completed()

    def test_save_and_load_with_installation_date(self) -> None:
        """インストール完了日時の保存と読み込みが正しく動作することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # 完了日時付きの状態を作成
            state = InstallationState()
            state.complete_installation()
            original_date = state.installation_date

            # 保存と読み込み
            adapter.save_installation_state(state)
            loaded_state = adapter.load_installation_state()

            # 日時が正しく復元されることを確認
            assert loaded_state.installation_date is not None
            assert loaded_state.installation_date == original_date

    def test_toml_format_is_correct(self) -> None:
        """生成されるTOMLファイルの形式が正しいことを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # テスト用の状態を作成
            state = InstallationState()
            state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
            state.mark_step_skipped(InstallationStep.OBS_SETUP)
            state.current_step = InstallationStep.FFMPEG_SETUP

            # 保存
            adapter.save_installation_state(state)

            # ファイル内容を確認
            content = file_path.read_text(encoding="utf-8")

            # 期待される内容が含まれていることを確認
            assert "[installer]" in content
            assert "is_completed = false" in content
            assert 'current_step = "ffmpeg_setup"' in content
            assert '"hardware_check"' in content
            assert '"obs_setup"' in content
            # installation_dateはNoneなので含まれていないことを確認
            assert "installation_date" not in content

    def test_handles_invalid_toml_data_gracefully(self) -> None:
        """不正なTOMLデータを適切に処理することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # 不正なデータを含むTOMLファイルを作成
            invalid_toml = """
[installer]
is_completed = false
current_step = "invalid_step"
completed_steps = ["invalid_step", "hardware_check"]
skipped_steps = []
installation_date = "invalid_date"
"""
            file_path.write_text(invalid_toml, encoding="utf-8")

            # 読み込み（エラーにならずに適切にフォールバックすることを確認）
            state = adapter.load_installation_state()

            # 有効なデータのみが読み込まれることを確認
            assert state.current_step == InstallationStep.HARDWARE_CHECK  # デフォルトにフォールバック
            assert InstallationStep.HARDWARE_CHECK in state.completed_steps  # 有効なステップのみ
            assert len(state.completed_steps) == 1  # 無効なステップは除外
            assert state.installation_date is None  # 無効な日時は無視

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows does not properly support directory permission restrictions"
    )
    def test_repository_error_on_file_permission_error(self) -> None:
        """ファイル権限エラー時にRepositoryErrorが発生することを確認する。"""
        # 読み取り専用ディレクトリでテスト（Unix系のみ）
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "readonly" / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # 親ディレクトリを作成して読み取り専用にする
            file_path.parent.mkdir()
            try:
                file_path.parent.chmod(0o444)  # 読み取り専用

                # 保存時にRepositoryErrorが発生することを確認
                state = InstallationState()
                with pytest.raises(RepositoryError):
                    adapter.save_installation_state(state)

            finally:
                # クリーンアップのために権限を戻す
                file_path.parent.chmod(0o755)

    def test_state_to_toml_dict_conversion(self) -> None:
        """状態からTOML辞書への変換が正しく動作することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # テスト用の状態を作成
            state = InstallationState()
            state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
            state.mark_step_skipped(InstallationStep.OBS_SETUP)
            state.current_step = InstallationStep.FFMPEG_SETUP
            state.complete_installation()

            # 内部メソッドをテスト
            toml_dict = adapter._state_to_toml_dict(state)

            # 変換結果を確認
            installer_data = toml_dict["installer"]
            assert installer_data["is_completed"] is True
            assert installer_data["current_step"] == "ffmpeg_setup"
            assert installer_data["completed_steps"] == ["hardware_check"]
            assert installer_data["skipped_steps"] == ["obs_setup"]
            assert installer_data["installation_date"] is not None

    def test_toml_dict_to_state_conversion(self) -> None:
        """TOML辞書から状態への変換が正しく動作することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "installer.toml"
            adapter = InstallationStateFileAdapter(file_path)

            # テスト用のTOML辞書を作成
            toml_dict = {
                "installer": {
                    "is_completed": True,
                    "current_step": "ffmpeg_setup",
                    "completed_steps": ["hardware_check"],
                    "skipped_steps": ["obs_setup"],
                    "installation_date": "2024-01-01T12:00:00",
                }
            }

            # 内部メソッドをテスト
            state = adapter._toml_dict_to_state(toml_dict)

            # 変換結果を確認
            assert state.is_completed is True
            assert state.current_step == InstallationStep.FFMPEG_SETUP
            assert state.completed_steps == [InstallationStep.HARDWARE_CHECK]
            assert state.skipped_steps == [InstallationStep.OBS_SETUP]
            assert state.installation_date is not None
            assert state.installation_date.year == 2024
