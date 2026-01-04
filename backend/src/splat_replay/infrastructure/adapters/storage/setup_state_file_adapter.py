"""TOMLファイルベースのセットアップ状態リポジトリ実装。

Clean Architectureの原則に基づき、責務を分離：
- SetupStateFileIO: ファイルI/O
- SetupStateSerializer: State変換
- SetupStateFileAdapter: リポジトリポートの薄いラッパー
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from structlog.stdlib import BoundLogger

from splat_replay.domain.models import SetupState, SetupStep
from splat_replay.domain.repositories import (
    RepositoryError,
    SetupStateRepository,
)
from splat_replay.infrastructure.logging import get_logger

from .setup_state_file_io import SetupStateFileIO
from .setup_state_serializer import SetupStateSerializer


class SetupStateFileAdapter(SetupStateRepository):
    """TOMLファイルベースのセットアップ状態リポジトリ実装。

    ファイルI/OとState変換を専用クラスに委譲し、
    このクラスはリポジトリポートの調整役に徹する。
    """

    def __init__(self, file_path: Path) -> None:
        """アダプターを初期化する。

        Args:
            file_path: セットアップ状態を保存するTOMLファイルのパス
        """
        self._logger: BoundLogger = get_logger()
        self._file_io = SetupStateFileIO(file_path, self._logger)
        self._serializer = SetupStateSerializer(self._logger)

    def save_installation_state(self, state: SetupState) -> None:
        """セットアップ状態をTOMLファイルに保存する。

        Args:
            state: 保存するセットアップ状態

        Raises:
            RepositoryError: 保存に失敗した場合
        """
        try:
            # State → TOML dict変換
            toml_data = self._serializer.state_to_dict(state)

            # ファイル書き込み
            self._file_io.write(toml_data)

            self._logger.info(
                "Installation state saved",
                is_completed=state.is_completed,
                current_step=state.current_step.value,
            )

        except Exception as e:
            error_msg = f"Failed to save installation state: {e}"
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def load_installation_state(self) -> SetupState:
        """TOMLファイルからインストール状態を読み込む。

        Returns:
            読み込まれたインストール状態。ファイルが存在しない場合はデフォルト状態を返す。

        Raises:
            RepositoryError: 読み込みに失敗した場合
        """
        try:
            if not self._file_io.exists():
                self._logger.info(
                    "Installation state file not found, returning default state"
                )
                return SetupState()

            # ファイル読み込み
            toml_data = self._file_io.read()

            # TOML dict → State変換
            state = self._serializer.dict_to_state(toml_data)

            self._logger.info(
                "Installation state loaded",
                is_completed=state.is_completed,
                current_step=state.current_step.value,
            )

            return state

        except Exception as e:
            error_msg = f"Failed to load installation state: {e}"
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)

    def mark_step_completed(self, step: SetupStep) -> None:
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
            state = replace(state, camera_permission_dialog_shown=True)

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
            state = replace(state, youtube_permission_dialog_shown=True)

            # 保存
            self.save_installation_state(state)

            self._logger.info("YouTube permission dialog marked as shown")

        except Exception as e:
            error_msg = (
                f"Failed to mark youtube permission dialog as shown: {e}"
            )
            self._logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg, cause=e)
