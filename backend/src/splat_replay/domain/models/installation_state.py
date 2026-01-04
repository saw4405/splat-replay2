"""セットアップ状態のドメインモデル。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class SetupStep(Enum):
    """セットアップステップの列挙型。"""

    HARDWARE_CHECK = "hardware_check"
    FFMPEG_SETUP = "ffmpeg_setup"
    OBS_SETUP = "obs_setup"
    TESSERACT_SETUP = "tesseract_setup"
    FONT_INSTALLATION = "font_installation"
    YOUTUBE_SETUP = "youtube_setup"

    @classmethod
    def get_all_steps(cls) -> List["SetupStep"]:
        """全てのセットアップステップを順序通りに取得する。"""
        return [
            cls.HARDWARE_CHECK,
            cls.FFMPEG_SETUP,
            cls.OBS_SETUP,
            cls.TESSERACT_SETUP,
            cls.FONT_INSTALLATION,
            cls.YOUTUBE_SETUP,
        ]

    def get_next_step(self) -> Optional["SetupStep"]:
        """次のステップを取得する。最後のステップの場合はNoneを返す。"""
        all_steps = self.get_all_steps()
        try:
            current_index = all_steps.index(self)
            if current_index < len(all_steps) - 1:
                return all_steps[current_index + 1]
        except ValueError:
            pass
        return None

    def get_previous_step(self) -> Optional["SetupStep"]:
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
        display_names: Dict[SetupStep, str] = {
            SetupStep.HARDWARE_CHECK: "ハードウェア確認",
            SetupStep.FFMPEG_SETUP: "FFMPEGセットアップ",
            SetupStep.OBS_SETUP: "OBSセットアップ",
            SetupStep.TESSERACT_SETUP: "Tesseractセットアップ",
            SetupStep.FONT_INSTALLATION: "フォントインストール",
            SetupStep.YOUTUBE_SETUP: "YouTube API設定",
        }
        result = display_names.get(self)
        return result if result is not None else self.value


@dataclass(frozen=True)
class SetupState:
    """セットアップ状態を管理するドメインエンティティ（不変）。"""

    is_completed: bool = False
    current_step: SetupStep = SetupStep.HARDWARE_CHECK
    completed_steps: tuple[SetupStep, ...] = ()
    skipped_steps: tuple[SetupStep, ...] = ()
    step_details: dict[str, dict[str, bool]] = field(default_factory=dict)
    installation_date: Optional[datetime] = None
    camera_permission_dialog_shown: bool = False
    youtube_permission_dialog_shown: bool = False

    def mark_step_completed(self, step: SetupStep) -> SetupState:
        """指定されたステップを完了済みとしてマークする（新しいインスタンスを返す）。"""
        # 既に完了済みの場合はそのまま返す
        if step in self.completed_steps:
            return self

        # 新しい completed_steps を作成
        new_completed = (*self.completed_steps, step)

        # skipped_steps から除外
        new_skipped = tuple(s for s in self.skipped_steps if s != step)

        return SetupState(
            is_completed=self.is_completed,
            current_step=self.current_step,
            completed_steps=new_completed,
            skipped_steps=new_skipped,
            step_details=self.step_details,
            installation_date=self.installation_date,
            camera_permission_dialog_shown=self.camera_permission_dialog_shown,
            youtube_permission_dialog_shown=self.youtube_permission_dialog_shown,
        )

    def mark_step_skipped(self, step: SetupStep) -> SetupState:
        """指定されたステップをスキップ済みとしてマークする（新しいインスタンスを返す）。"""
        # 既にスキップ済みの場合はそのまま返す
        if step in self.skipped_steps:
            return self

        # 新しい skipped_steps を作成
        new_skipped = (*self.skipped_steps, step)

        # completed_steps から除外
        new_completed = tuple(s for s in self.completed_steps if s != step)

        return SetupState(
            is_completed=self.is_completed,
            current_step=self.current_step,
            completed_steps=new_completed,
            skipped_steps=new_skipped,
            step_details=self.step_details,
            installation_date=self.installation_date,
            camera_permission_dialog_shown=self.camera_permission_dialog_shown,
            youtube_permission_dialog_shown=self.youtube_permission_dialog_shown,
        )

    def is_step_completed(self, step: SetupStep) -> bool:
        """指定されたステップが完了済みかどうかを確認する。"""
        return step in self.completed_steps

    def is_step_skipped(self, step: SetupStep) -> bool:
        """指定されたステップがスキップ済みかどうかを確認する。"""
        return step in self.skipped_steps

    def mark_substep_completed(
        self, step: SetupStep, substep_id: str, completed: bool = True
    ) -> SetupState:
        """指定されたサブステップを完了済みとしてマークする（新しいインスタンスを返す）。"""
        step_key = step.value
        new_step_details = {**self.step_details}

        if step_key not in new_step_details:
            new_step_details[step_key] = {}
        else:
            # ネストした辞書もコピー
            new_step_details[step_key] = {**new_step_details[step_key]}

        new_step_details[step_key][substep_id] = completed

        return SetupState(
            is_completed=self.is_completed,
            current_step=self.current_step,
            completed_steps=self.completed_steps,
            skipped_steps=self.skipped_steps,
            step_details=new_step_details,
            installation_date=self.installation_date,
            camera_permission_dialog_shown=self.camera_permission_dialog_shown,
            youtube_permission_dialog_shown=self.youtube_permission_dialog_shown,
        )

    def is_substep_completed(self, step: SetupStep, substep_id: str) -> bool:
        """指定されたサブステップが完了済みかどうかを確認する。"""
        step_key = step.value
        if step_key not in self.step_details:
            return False
        return self.step_details[step_key].get(substep_id, False)

    def get_step_details(self, step: SetupStep) -> Dict[str, bool]:
        """指定されたステップのサブステップ詳細を取得する。"""
        step_key = step.value
        return self.step_details.get(step_key, {})

    def can_proceed_to_next_step(self) -> bool:
        """次のステップに進むことができるかどうかを確認する。"""
        return self.is_step_completed(
            self.current_step
        ) or self.is_step_skipped(self.current_step)

    def proceed_to_next_step(self) -> tuple[bool, SetupState]:
        """次のステップに進む（新しいインスタンスを返す）。

        Returns:
            (成功フラグ, 新しいインスタンス)のタプル
        """
        if not self.can_proceed_to_next_step():
            return (False, self)

        next_step = self.current_step.get_next_step()
        if next_step is None:
            # 全てのステップが完了
            new_state = self.complete_installation()
            return (True, new_state)

        return (
            True,
            SetupState(
                is_completed=self.is_completed,
                current_step=next_step,
                completed_steps=self.completed_steps,
                skipped_steps=self.skipped_steps,
                step_details=self.step_details,
                installation_date=self.installation_date,
                camera_permission_dialog_shown=self.camera_permission_dialog_shown,
                youtube_permission_dialog_shown=self.youtube_permission_dialog_shown,
            ),
        )

    def go_back_to_previous_step(self) -> tuple[bool, SetupState]:
        """前のステップに戻る（新しいインスタンスを返す）。

        Returns:
            (成功フラグ, 新しいインスタンス)のタプル
        """
        previous_step = self.current_step.get_previous_step()
        if previous_step is None:
            return (False, self)

        return (
            True,
            SetupState(
                is_completed=self.is_completed,
                current_step=previous_step,
                completed_steps=self.completed_steps,
                skipped_steps=self.skipped_steps,
                step_details=self.step_details,
                installation_date=self.installation_date,
                camera_permission_dialog_shown=self.camera_permission_dialog_shown,
                youtube_permission_dialog_shown=self.youtube_permission_dialog_shown,
            ),
        )

    def complete_installation(self) -> SetupState:
        """セットアップを完了状態にする（新しいインスタンスを返す）。"""
        return SetupState(
            is_completed=True,
            current_step=self.current_step,
            completed_steps=self.completed_steps,
            skipped_steps=self.skipped_steps,
            step_details=self.step_details,
            installation_date=datetime.now(),
            camera_permission_dialog_shown=self.camera_permission_dialog_shown,
            youtube_permission_dialog_shown=self.youtube_permission_dialog_shown,
        )

    def get_progress_percentage(self) -> float:
        """セットアップ進行状況をパーセンテージで取得する。"""
        all_steps = SetupStep.get_all_steps()
        total_steps = len(all_steps)

        if total_steps == 0:
            return 100.0

        processed_steps = len(self.completed_steps) + len(self.skipped_steps)
        return (processed_steps / total_steps) * 100.0

    def get_remaining_steps(self) -> List[SetupStep]:
        """残りのステップリストを取得する。"""
        all_steps = SetupStep.get_all_steps()
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
        if self.current_step not in SetupStep.get_all_steps():
            return False

        return True

    class Config:
        """Pydantic設定。"""

        use_enum_values = False  # Enumオブジェクトとして保持
        validate_assignment = True
