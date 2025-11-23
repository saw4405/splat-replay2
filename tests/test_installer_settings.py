"""インストーラー設定のテスト。"""

import tempfile
from datetime import datetime
from pathlib import Path

from splat_replay.domain.models import InstallationState, InstallationStep
from splat_replay.shared.config.app import AppSettings
from splat_replay.shared.config.installer import InstallerSettings


class TestInstallerSettings:
    """InstallerSettingsのテストクラス。"""

    def test_default_installer_settings(self) -> None:
        """デフォルトのインストーラー設定が正しいことを確認する。"""
        settings = InstallerSettings()

        assert not settings.is_completed
        assert settings.current_step == "hardware_check"
        assert settings.completed_steps == []
        assert settings.skipped_steps == []
        assert settings.installation_date is None

        # 各ステップの詳細設定もデフォルト値であることを確認
        assert not settings.hardware.required_items_confirmed
        assert not settings.obs.installation_confirmed
        assert not settings.ffmpeg.installation_confirmed
        assert not settings.tesseract.use_ocr
        assert not settings.font.ikamoji_font_installed
        assert not settings.youtube.api_enabled

    def test_to_installation_state_conversion(self) -> None:
        """設定からInstallationStateへの変換が正しく動作することを確認する。"""
        settings = InstallerSettings(
            is_completed=True,
            current_step="ffmpeg_setup",
            completed_steps=["hardware_check", "obs_setup"],
            skipped_steps=["tesseract_setup"],
            installation_date="2024-01-01T12:00:00",
        )

        state = settings.to_installation_state()

        assert state.is_completed is True
        assert state.current_step == InstallationStep.FFMPEG_SETUP
        assert state.completed_steps == [
            InstallationStep.HARDWARE_CHECK,
            InstallationStep.OBS_SETUP,
        ]
        assert state.skipped_steps == [InstallationStep.TESSERACT_SETUP]
        assert state.installation_date is not None
        assert state.installation_date.year == 2024

    def test_from_installation_state_conversion(self) -> None:
        """InstallationStateから設定への変換が正しく動作することを確認する。"""
        state = InstallationState()
        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        state.mark_step_skipped(InstallationStep.OBS_SETUP)
        state.current_step = InstallationStep.FFMPEG_SETUP
        state.complete_installation()

        settings = InstallerSettings.from_installation_state(state)

        assert settings.is_completed is True
        assert settings.current_step == "ffmpeg_setup"
        assert settings.completed_steps == ["hardware_check"]
        assert settings.skipped_steps == ["obs_setup"]
        assert settings.installation_date is not None

    def test_handles_invalid_step_values_gracefully(self) -> None:
        """無効なステップ値を適切に処理することを確認する。"""
        settings = InstallerSettings(
            current_step="invalid_step",
            completed_steps=["hardware_check", "invalid_step"],
            skipped_steps=["invalid_step2", "obs_setup"],
        )

        state = settings.to_installation_state()

        # 無効なステップはデフォルトにフォールバック
        assert state.current_step == InstallationStep.HARDWARE_CHECK
        # 有効なステップのみが含まれる
        assert state.completed_steps == [InstallationStep.HARDWARE_CHECK]
        assert state.skipped_steps == [InstallationStep.OBS_SETUP]

    def test_handles_invalid_date_gracefully(self) -> None:
        """無効な日時文字列を適切に処理することを確認する。"""
        settings = InstallerSettings(
            installation_date="invalid_date_format"
        )

        state = settings.to_installation_state()

        # 無効な日時はNoneになる
        assert state.installation_date is None


class TestAppSettingsIntegration:
    """AppSettingsとの統合テスト。"""

    def test_app_settings_includes_installer_section(self) -> None:
        """AppSettingsにインストーラーセクションが含まれることを確認する。"""
        settings = AppSettings()

        assert hasattr(settings, 'installer')
        assert isinstance(settings.installer, InstallerSettings)

    def test_app_settings_toml_serialization_with_installer(self) -> None:
        """インストーラー設定を含むAppSettingsのTOMLシリアライゼーションが正しく動作することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_settings.toml"

            # インストーラー設定を変更
            settings = AppSettings()
            settings.installer.is_completed = True
            settings.installer.current_step = "obs_setup"
            settings.installer.hardware.required_items_confirmed = True

            # 保存
            settings.save_to_toml(file_path)

            # ファイルが作成されることを確認
            assert file_path.exists()

            # 内容を確認
            content = file_path.read_text(encoding="utf-8")
            assert "[installer]" in content
            assert "is_completed = true" in content
            assert 'current_step = "obs_setup"' in content
            assert "[installer.hardware]" in content
            assert "required_items_confirmed = true" in content

    def test_app_settings_toml_deserialization_with_installer(self) -> None:
        """インストーラー設定を含むTOMLファイルからのAppSettings読み込みが正しく動作することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_settings.toml"

            # テスト用のTOMLファイルを作成
            toml_content = """
[installer]
is_completed = true
current_step = "ffmpeg_setup"
completed_steps = ["hardware_check", "obs_setup"]
skipped_steps = ["tesseract_setup"]
installation_date = "2024-01-01T12:00:00"

[installer.hardware]
required_items_confirmed = true
connection_diagram_viewed = false

[installer.obs]
installation_confirmed = true
ndi_plugin_installed = false

[installer.ffmpeg]
installation_confirmed = false
environment_variable_set = true

[installer.tesseract]
use_ocr = true
installation_confirmed = false

[installer.font]
ikamoji_font_installed = true

[installer.youtube]
api_enabled = false
credentials_configured = true
"""
            file_path.write_text(toml_content, encoding="utf-8")

            # 読み込み
            settings = AppSettings.load_from_toml(file_path)

            # インストーラー設定が正しく読み込まれることを確認
            assert settings.installer.is_completed is True
            assert settings.installer.current_step == "ffmpeg_setup"
            assert settings.installer.completed_steps == [
                "hardware_check", "obs_setup"]
            assert settings.installer.skipped_steps == ["tesseract_setup"]
            assert settings.installer.installation_date == "2024-01-01T12:00:00"

            # 詳細設定も正しく読み込まれることを確認
            assert settings.installer.hardware.required_items_confirmed is True
            assert settings.installer.hardware.connection_diagram_viewed is False
            assert settings.installer.obs.installation_confirmed is True
            assert settings.installer.obs.ndi_plugin_installed is False
            assert settings.installer.ffmpeg.installation_confirmed is False
            assert settings.installer.ffmpeg.environment_variable_set is True
            assert settings.installer.tesseract.use_ocr is True
            assert settings.installer.tesseract.installation_confirmed is False
            assert settings.installer.font.ikamoji_font_installed is True
            assert settings.installer.youtube.api_enabled is False
            assert settings.installer.youtube.credentials_configured is True

    def test_app_settings_roundtrip_with_installer(self) -> None:
        """インストーラー設定を含むAppSettingsの保存・読み込みの往復が正しく動作することを確認する。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_settings.toml"

            # 元の設定を作成
            original_settings = AppSettings()
            original_settings.installer.is_completed = True
            original_settings.installer.current_step = "youtube_setup"
            original_settings.installer.completed_steps = [
                "hardware_check", "obs_setup", "ffmpeg_setup"
            ]
            original_settings.installer.hardware.required_items_confirmed = True
            original_settings.installer.obs.installation_confirmed = True
            original_settings.installer.ffmpeg.environment_variable_set = True

            # 保存
            original_settings.save_to_toml(file_path)

            # 読み込み
            loaded_settings = AppSettings.load_from_toml(file_path)

            # 設定が正しく復元されることを確認
            assert loaded_settings.installer.is_completed == original_settings.installer.is_completed
            assert loaded_settings.installer.current_step == original_settings.installer.current_step
            assert loaded_settings.installer.completed_steps == original_settings.installer.completed_steps
            assert (
                loaded_settings.installer.hardware.required_items_confirmed
                == original_settings.installer.hardware.required_items_confirmed
            )
            assert (
                loaded_settings.installer.obs.installation_confirmed
                == original_settings.installer.obs.installation_confirmed
            )
            assert (
                loaded_settings.installer.ffmpeg.environment_variable_set
                == original_settings.installer.ffmpeg.environment_variable_set
            )
