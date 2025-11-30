"""TOMLファイルベースのインストール状態リポジトリ実装。"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict

import tomli_w
from structlog.stdlib import BoundLogger

from splat_replay.domain.models import InstallationState, InstallationStep
from splat_replay.domain.repositories import (
    InstallationStateRepository,
    RepositoryError,
)
from splat_replay.shared.logger import get_logger


class InstallationStateFileAdapter(InstallationStateRepository):
    """TOMLファイルベースのインストール状態リポジトリ実装。"""

    def __init__(self, file_path: Path) -> None:
        """アダプターを初期化する。

        Args:
            file_path: インストール状態を保存するTOMLファイルのパス
        """
        self._file_path = file_path
        self._logger: BoundLogger = get_logger()

    def save_installation_state(self, state: InstallationState) -> None:
        """インストール状態をTOMLファイルに保存する。

        Args:
            state: 保存するインストール状態

        Raises:
            RepositoryError: 保存に失敗した場合
        """
        try:
            # ディレクトリが存在しない場合は作成
            self._file_path.parent.mkdir(parents=True, exist_ok=True)

            # インストール状態をTOML形式に変換
            toml_data = self._state_to_toml_dict(state)

            # TOMLファイルに書き込み
            toml_text = tomli_w.dumps(toml_data)
            self._file_path.write_text(toml_text, encoding="utf-8")

            self._logger.info(
                "Installation state saved",
                file_path=str(self._file_path),
                is_completed=state.is_completed,
                current_step=state.current_step.value,
            )

        except Exception as e:
            error_msg = (
                f"Failed to save installation state to {self._file_path}: {e}"
            )
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def load_installation_state(self) -> InstallationState:
        """TOMLファイルからインストール状態を読み込む。

        Returns:
            読み込まれたインストール状態。ファイルが存在しない場合はデフォルト状態を返す。

        Raises:
            RepositoryError: 読み込みに失敗した場合
        """
        try:
            if not self._file_path.exists():
                self._logger.info(
                    "Installation state file not found, returning default state",
                    file_path=str(self._file_path),
                )
                return InstallationState()

            # TOMLファイルを読み込み
            with self._file_path.open("rb") as f:
                toml_data = tomllib.load(f)

            # インストール状態に変換
            state = self._toml_dict_to_state(toml_data)

            self._logger.info(
                "Installation state loaded",
                file_path=str(self._file_path),
                is_completed=state.is_completed,
                current_step=state.current_step.value,
            )

            return state

        except Exception as e:
            error_msg = f"Failed to load installation state from {self._file_path}: {e}"
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def mark_step_completed(self, step: InstallationStep) -> None:
        """指定されたステップを完了済みとしてマークし、永続化する。

        Args:
            step: 完了済みとしてマークするステップ

        Raises:
            RepositoryError: 更新に失敗した場合
        """
        try:
            # 現在の状態を読み込み
            state = self.load_installation_state()

            # ステップを完了済みとしてマーク
            state.mark_step_completed(step)

            # 保存
            self.save_installation_state(state)

            self._logger.info(
                "Step marked as completed",
                step=step.value,
                step_display_name=step.get_display_name(),
            )

        except Exception as e:
            error_msg = f"Failed to mark step {step.value} as completed: {e}"
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def is_installation_completed(self) -> bool:
        """インストールが完了しているかどうかを確認する。

        Returns:
            インストールが完了している場合はTrue、そうでなければFalse

        Raises:
            RepositoryError: 確認に失敗した場合
        """
        try:
            state = self.load_installation_state()
            return state.is_completed

        except Exception as e:
            error_msg = f"Failed to check installation completion status: {e}"
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def is_camera_permission_dialog_shown(self) -> bool:
        """カメラ許可ダイアログが表示済みかどうかを確認する。

        Returns:
            表示済みの場合はTrue、そうでなければFalse

        Raises:
            RepositoryError: 確認に失敗した場合
        """
        try:
            state = self.load_installation_state()
            return state.camera_permission_dialog_shown

        except Exception as e:
            error_msg = f"Failed to check camera permission dialog status: {e}"
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def mark_camera_permission_dialog_shown(self) -> None:
        """カメラ許可ダイアログを表示済みとしてマークし、永続化する。

        Raises:
            RepositoryError: 更新に失敗した場合
        """
        try:
            # 現在の状態を読み込み
            state = self.load_installation_state()

            # フラグを更新
            state.camera_permission_dialog_shown = True

            # 保存
            self.save_installation_state(state)

            self._logger.info("Camera permission dialog marked as shown")

        except Exception as e:
            error_msg = (
                f"Failed to mark camera permission dialog as shown: {e}"
            )
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def is_youtube_permission_dialog_shown(self) -> bool:
        """YouTube権限ダイアログが表示済みかどうかを確認する。

        Returns:
            表示済みの場合はTrue、そうでなければFalse

        Raises:
            RepositoryError: 確認に失敗した場合
        """
        try:
            state = self.load_installation_state()
            return state.youtube_permission_dialog_shown

        except Exception as e:
            error_msg = (
                f"Failed to check youtube permission dialog status: {e}"
            )
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def mark_youtube_permission_dialog_shown(self) -> None:
        """YouTube権限ダイアログを表示済みとしてマークし、永続化する。

        Raises:
            RepositoryError: 更新に失敗した場合
        """
        try:
            # 現在の状態を読み込み
            state = self.load_installation_state()

            # フラグを更新
            state.youtube_permission_dialog_shown = True

            # 保存
            self.save_installation_state(state)

            self._logger.info("YouTube permission dialog marked as shown")

        except Exception as e:
            error_msg = (
                f"Failed to mark youtube permission dialog as shown: {e}"
            )
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def _state_to_toml_dict(self, state: InstallationState) -> Dict[str, Any]:
        """InstallationStateをTOML辞書形式に変換する。

        Args:
            state: 変換するインストール状態

        Returns:
            TOML辞書形式のデータ
        """
        installer_data: Dict[str, Any] = {
            "is_completed": state.is_completed,
            "current_step": state.current_step.value,
            "completed_steps": [step.value for step in state.completed_steps],
            "skipped_steps": [step.value for step in state.skipped_steps],
            "step_details": state.step_details,
            "camera_permission_dialog_shown": state.camera_permission_dialog_shown,
            "youtube_permission_dialog_shown": state.youtube_permission_dialog_shown,
        }

        # installation_dateがNoneでない場合のみ追加（TOMLはNoneをサポートしないため）
        if state.installation_date is not None:
            installer_data["installation_date"] = (
                state.installation_date.isoformat()
            )

        return {"installer": installer_data}

    def _toml_dict_to_state(
        self, toml_data: Dict[str, Any]
    ) -> InstallationState:
        """TOML辞書形式のデータをInstallationStateに変換する。

        Args:
            toml_data: TOML辞書形式のデータ

        Returns:
            変換されたインストール状態

        Raises:
            ValueError: データ形式が不正な場合
        """
        installer_data = toml_data.get("installer", {})

        # 基本データの取得
        is_completed = installer_data.get("is_completed", False)
        current_step_value = installer_data.get(
            "current_step", "hardware_check"
        )
        completed_steps_values = installer_data.get("completed_steps", [])
        skipped_steps_values = installer_data.get("skipped_steps", [])
        step_details = installer_data.get("step_details", {})
        installation_date_str = installer_data.get("installation_date")
        camera_permission_dialog_shown = installer_data.get(
            "camera_permission_dialog_shown", False
        )
        youtube_permission_dialog_shown = installer_data.get(
            "youtube_permission_dialog_shown", False
        )

        # Enumに変換
        try:
            current_step = InstallationStep(current_step_value)
        except ValueError:
            self._logger.warning(
                "Invalid current_step value, using default",
                current_step_value=current_step_value,
            )
            current_step = InstallationStep.HARDWARE_CHECK

        completed_steps = []
        for step_value in completed_steps_values:
            try:
                completed_steps.append(InstallationStep(step_value))
            except ValueError:
                self._logger.warning(
                    "Invalid completed step value, skipping",
                    step_value=step_value,
                )

        skipped_steps = []
        for step_value in skipped_steps_values:
            try:
                skipped_steps.append(InstallationStep(step_value))
            except ValueError:
                self._logger.warning(
                    "Invalid skipped step value, skipping",
                    step_value=step_value,
                )

        # 日時の変換
        installation_date = None
        if installation_date_str:
            try:
                from datetime import datetime

                installation_date = datetime.fromisoformat(
                    installation_date_str
                )
            except ValueError:
                self._logger.warning(
                    "Invalid installation_date format, ignoring",
                    installation_date_str=installation_date_str,
                )

        # InstallationStateを作成
        return InstallationState(
            is_completed=is_completed,
            current_step=current_step,
            completed_steps=completed_steps,
            skipped_steps=skipped_steps,
            step_details=step_details,
            installation_date=installation_date,
            camera_permission_dialog_shown=camera_permission_dialog_shown,
            youtube_permission_dialog_shown=youtube_permission_dialog_shown,
        )
