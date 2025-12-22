"""インストール状態のドメインモデル。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class InstallationStep(Enum):
    """インストールステップの列挙型。"""

    HARDWARE_CHECK = "hardware_check"
    FFMPEG_SETUP = "ffmpeg_setup"
    OBS_SETUP = "obs_setup"
    TESSERACT_SETUP = "tesseract_setup"
    FONT_INSTALLATION = "font_installation"
    YOUTUBE_SETUP = "youtube_setup"

    @classmethod
    def get_all_steps(cls) -> List["InstallationStep"]:
        """全てのインストールステップを順序通りに取得する。"""
        return [
            cls.HARDWARE_CHECK,
            cls.FFMPEG_SETUP,
            cls.OBS_SETUP,
            cls.TESSERACT_SETUP,
            cls.FONT_INSTALLATION,
            cls.YOUTUBE_SETUP,
        ]

    def get_next_step(self) -> Optional["InstallationStep"]:
        """次のステップを取得する。最後のステップの場合はNoneを返す。"""
        all_steps = self.get_all_steps()
        try:
            current_index = all_steps.index(self)
            if current_index < len(all_steps) - 1:
                return all_steps[current_index + 1]
        except ValueError:
            pass
        return None

    def get_previous_step(self) -> Optional["InstallationStep"]:
        """前のステップを取得する。最初のステップの場合はNoneを返す。"""
        all_steps = self.get_all_steps()
        try:
            current_index = all_steps.index(self)
            if current_index > 0:
                return all_steps[current_index - 1]
        except ValueError:
            pass
        return None

    def get_display_name(self) -> str:
        """ステップの表示名を取得する。"""
        display_names: Dict[InstallationStep, str] = {
            InstallationStep.HARDWARE_CHECK: "ハードウェア確認",
            InstallationStep.FFMPEG_SETUP: "FFMPEGセットアップ",
            InstallationStep.OBS_SETUP: "OBSセットアップ",
            InstallationStep.TESSERACT_SETUP: "Tesseractセットアップ",
            InstallationStep.FONT_INSTALLATION: "フォントインストール",
            InstallationStep.YOUTUBE_SETUP: "YouTube API設定",
        }
        result = display_names.get(self)
        return result if result is not None else self.value


class InstallationState(BaseModel):
    """インストール状態を管理するドメインエンティティ。"""

    is_completed: bool = Field(
        default=False, description="インストールが完了しているかどうか"
    )
    current_step: InstallationStep = Field(
        default=InstallationStep.HARDWARE_CHECK,
        description="現在のインストールステップ",
    )
    completed_steps: List[InstallationStep] = Field(
        default_factory=list, description="完了済みのステップリスト"
    )
    skipped_steps: List[InstallationStep] = Field(
        default_factory=list, description="スキップされたステップリスト"
    )
    step_details: Dict[str, Dict[str, bool]] = Field(
        default_factory=dict,
        description="各セットアップステップの詳細な進捗状況（ステップID -> サブステップID -> 完了状態）",
    )
    installation_date: Optional[datetime] = Field(
        default=None, description="インストール完了日時"
    )
    camera_permission_dialog_shown: bool = Field(
        default=False, description="カメラ許可ダイアログが表示済みかどうか"
    )
    youtube_permission_dialog_shown: bool = Field(
        default=False, description="YouTube権限ダイアログが表示済みかどうか"
    )

    def mark_step_completed(self, step: InstallationStep) -> None:
        """指定されたステップを完了済みとしてマークする。"""
        if step not in self.completed_steps:
            self.completed_steps.append(step)

        # スキップリストから削除（完了したため）
        if step in self.skipped_steps:
            self.skipped_steps.remove(step)

    def mark_step_skipped(self, step: InstallationStep) -> None:
        """指定されたステップをスキップ済みとしてマークする。"""
        if step not in self.skipped_steps:
            self.skipped_steps.append(step)

        # 完了リストから削除（スキップしたため）
        if step in self.completed_steps:
            self.completed_steps.remove(step)

    def is_step_completed(self, step: InstallationStep) -> bool:
        """指定されたステップが完了済みかどうかを確認する。"""
        return step in self.completed_steps

    def is_step_skipped(self, step: InstallationStep) -> bool:
        """指定されたステップがスキップ済みかどうかを確認する。"""
        return step in self.skipped_steps

    def mark_substep_completed(
        self, step: InstallationStep, substep_id: str, completed: bool = True
    ) -> None:
        """指定されたサブステップを完了済みとしてマークする。"""
        step_key = step.value
        if step_key not in self.step_details:
            self.step_details[step_key] = {}
        self.step_details[step_key][substep_id] = completed

    def is_substep_completed(
        self, step: InstallationStep, substep_id: str
    ) -> bool:
        """指定されたサブステップが完了済みかどうかを確認する。"""
        step_key = step.value
        if step_key not in self.step_details:
            return False
        return self.step_details[step_key].get(substep_id, False)

    def get_step_details(self, step: InstallationStep) -> Dict[str, bool]:
        """指定されたステップのサブステップ詳細を取得する。"""
        step_key = step.value
        return self.step_details.get(step_key, {})

    def can_proceed_to_next_step(self) -> bool:
        """次のステップに進むことができるかどうかを確認する。"""
        return self.is_step_completed(
            self.current_step
        ) or self.is_step_skipped(self.current_step)

    def proceed_to_next_step(self) -> bool:
        """次のステップに進む。進めた場合はTrue、進めなかった場合はFalseを返す。"""
        if not self.can_proceed_to_next_step():
            return False

        next_step = self.current_step.get_next_step()
        if next_step is None:
            # 全てのステップが完了
            self.complete_installation()
            return True

        self.current_step = next_step
        return True

    def go_back_to_previous_step(self) -> bool:
        """前のステップに戻る。戻れた場合はTrue、戻れなかった場合はFalseを返す。"""
        previous_step = self.current_step.get_previous_step()
        if previous_step is None:
            return False

        self.current_step = previous_step
        return True

    def complete_installation(self) -> None:
        """インストールを完了状態にする。"""
        self.is_completed = True
        self.installation_date = datetime.now()

    def get_progress_percentage(self) -> float:
        """インストール進行状況をパーセンテージで取得する。"""
        all_steps = InstallationStep.get_all_steps()
        total_steps = len(all_steps)

        if total_steps == 0:
            return 100.0

        processed_steps = len(self.completed_steps) + len(self.skipped_steps)
        return (processed_steps / total_steps) * 100.0

    def get_remaining_steps(self) -> List[InstallationStep]:
        """残りのステップリストを取得する。"""
        all_steps = InstallationStep.get_all_steps()
        processed_steps = set(self.completed_steps + self.skipped_steps)
        return [step for step in all_steps if step not in processed_steps]

    def validate_state_consistency(self) -> bool:
        """状態の整合性を検証する。"""
        # 同じステップが完了とスキップの両方にある場合は不整合
        overlap = set(self.completed_steps) & set(self.skipped_steps)
        if overlap:
            return False

        # 完了状態なのに完了日時がない場合は不整合
        if self.is_completed and self.installation_date is None:
            return False

        # 現在のステップが有効な値かチェック
        if self.current_step not in InstallationStep.get_all_steps():
            return False

        return True

    class Config:
        """Pydantic設定。"""

        use_enum_values = False  # Enumオブジェクトとして保持
        validate_assignment = True
