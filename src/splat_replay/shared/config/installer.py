"""インストーラー設定モデル。"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from splat_replay.domain.models import InstallationStep


class HardwareSettings(BaseModel):
    """ハードウェア設定。"""

    required_items_confirmed: bool = Field(
        default=False,
        title="必要機材の確認完了",
        description="必要なハードウェア機材の確認が完了しているかどうか",
    )
    connection_diagram_viewed: bool = Field(
        default=False,
        title="接続図の確認完了",
        description="ハードウェア接続図の確認が完了しているかどうか",
    )


class OBSSettings(BaseModel):
    """OBS設定。"""

    installation_confirmed: bool = Field(
        default=False,
        title="OBSインストール確認完了",
        description="OBSのインストール状態の確認が完了しているかどうか",
    )
    ndi_plugin_installed: bool = Field(
        default=False,
        title="obs-ndiプラグインインストール完了",
        description="obs-ndiプラグインのインストールが完了しているかどうか",
    )
    ndi_runtime_installed: bool = Field(
        default=False,
        title="NDI 6 Runtimeインストール完了",
        description="NDI 6 Runtimeのインストールが完了しているかどうか",
    )
    recording_settings_configured: bool = Field(
        default=False,
        title="録画設定の構成完了",
        description="OBSの録画設定の構成が完了しているかどうか",
    )
    ndi_settings_configured: bool = Field(
        default=False,
        title="NDI設定の構成完了",
        description="OBSのNDI設定の構成が完了しているかどうか",
    )


class FFMPEGSettings(BaseModel):
    """FFMPEG設定。"""

    installation_confirmed: bool = Field(
        default=False,
        title="FFMPEGインストール確認完了",
        description="FFMPEGのインストール状態の確認が完了しているかどうか",
    )
    environment_variable_set: bool = Field(
        default=False,
        title="環境変数設定完了",
        description="FFMPEGの環境変数設定が完了しているかどうか",
    )


class TesseractSettings(BaseModel):
    """Tesseract設定。"""

    use_ocr: bool = Field(
        default=False,
        title="文字認識機能を使用する",
        description="Tesseractを使用した文字認識機能を使用するかどうか",
    )
    installation_confirmed: bool = Field(
        default=False,
        title="Tesseractインストール確認完了",
        description="Tesseractのインストール状態の確認が完了しているかどうか",
    )
    language_data_installed: bool = Field(
        default=False,
        title="言語データインストール完了",
        description="Tesseractの追加言語データのインストールが完了しているかどうか",
    )
    environment_variable_set: bool = Field(
        default=False,
        title="環境変数設定完了",
        description="Tesseractの環境変数設定が完了しているかどうか",
    )


class FontSettings(BaseModel):
    """フォント設定。"""

    ikamoji_font_installed: bool = Field(
        default=False,
        title="イカモドキフォントインストール完了",
        description="イカモドキフォントのインストールが完了しているかどうか",
    )


class YouTubeSettings(BaseModel):
    """YouTube設定。"""

    api_enabled: bool = Field(
        default=False,
        title="YouTube Data API有効化完了",
        description="YouTube Data APIの有効化が完了しているかどうか",
    )
    credentials_configured: bool = Field(
        default=False,
        title="認証情報設定完了",
        description="YouTube API認証情報の設定が完了しているかどうか",
    )


class InstallerSettings(BaseModel):
    """インストーラー設定。"""

    is_completed: bool = Field(
        default=False,
        title="インストール完了",
        description="インストーラーによるセットアップが完了しているかどうか",
    )
    current_step: str = Field(
        default="hardware_check",
        title="現在のステップ",
        description="現在のインストールステップ",
    )
    completed_steps: List[str] = Field(
        default_factory=list,
        title="完了済みステップ",
        description="完了済みのインストールステップのリスト",
    )
    skipped_steps: List[str] = Field(
        default_factory=list,
        title="スキップ済みステップ",
        description="スキップされたインストールステップのリスト",
    )
    installation_date: Optional[str] = Field(
        default=None,
        title="インストール完了日時",
        description="インストールが完了した日時（ISO形式）",
    )

    # 各ステップの詳細設定
    hardware: HardwareSettings = Field(
        default_factory=HardwareSettings,
        title="ハードウェア設定",
        description="ハードウェア確認に関する設定",
    )
    obs: OBSSettings = Field(
        default_factory=OBSSettings,
        title="OBS設定",
        description="OBSセットアップに関する設定",
    )
    ffmpeg: FFMPEGSettings = Field(
        default_factory=FFMPEGSettings,
        title="FFMPEG設定",
        description="FFMPEGセットアップに関する設定",
    )
    tesseract: TesseractSettings = Field(
        default_factory=TesseractSettings,
        title="Tesseract設定",
        description="Tesseractセットアップに関する設定",
    )
    font: FontSettings = Field(
        default_factory=FontSettings,
        title="フォント設定",
        description="フォントインストールに関する設定",
    )
    youtube: YouTubeSettings = Field(
        default_factory=YouTubeSettings,
        title="YouTube設定",
        description="YouTube API設定に関する設定",
    )

    def to_installation_state(self) -> "InstallationState":
        """設定からInstallationStateドメインモデルに変換する。

        Returns:
            変換されたInstallationStateオブジェクト
        """
        from splat_replay.domain.models import InstallationState, InstallationStep

        # ステップ文字列をEnumに変換
        try:
            current_step = InstallationStep(self.current_step)
        except ValueError:
            current_step = InstallationStep.HARDWARE_CHECK

        completed_steps = []
        for step_str in self.completed_steps:
            try:
                completed_steps.append(InstallationStep(step_str))
            except ValueError:
                continue

        skipped_steps = []
        for step_str in self.skipped_steps:
            try:
                skipped_steps.append(InstallationStep(step_str))
            except ValueError:
                continue

        # 日時の変換
        installation_date = None
        if self.installation_date:
            try:
                installation_date = datetime.fromisoformat(
                    self.installation_date)
            except ValueError:
                pass

        return InstallationState(
            is_completed=self.is_completed,
            current_step=current_step,
            completed_steps=completed_steps,
            skipped_steps=skipped_steps,
            installation_date=installation_date,
        )

    @classmethod
    def from_installation_state(cls, state: "InstallationState") -> "InstallerSettings":
        """InstallationStateドメインモデルから設定に変換する。

        Args:
            state: 変換元のInstallationStateオブジェクト

        Returns:
            変換されたInstallerSettingsオブジェクト
        """
        return cls(
            is_completed=state.is_completed,
            current_step=state.current_step.value,
            completed_steps=[step.value for step in state.completed_steps],
            skipped_steps=[step.value for step in state.skipped_steps],
            installation_date=(
                state.installation_date.isoformat()
                if state.installation_date
                else None
            ),
        )

    class Config:
        """Pydantic設定。"""

        validate_assignment = True
