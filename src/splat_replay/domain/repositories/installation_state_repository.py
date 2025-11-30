"""インストール状態リポジトリのインターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from splat_replay.domain.models import InstallationState, InstallationStep


class InstallationStateRepository(ABC):
    """インストール状態の永続化を担当するリポジトリインターフェース。"""

    @abstractmethod
    def save_installation_state(self, state: InstallationState) -> None:
        """インストール状態を保存する。

        Args:
            state: 保存するインストール状態

        Raises:
            RepositoryError: 保存に失敗した場合
        """
        pass

    @abstractmethod
    def load_installation_state(self) -> InstallationState:
        """インストール状態を読み込む。

        Returns:
            読み込まれたインストール状態。存在しない場合はデフォルト状態を返す。

        Raises:
            RepositoryError: 読み込みに失敗した場合
        """
        pass

    @abstractmethod
    def mark_step_completed(self, step: InstallationStep) -> None:
        """指定されたステップを完了済みとしてマークし、永続化する。

        Args:
            step: 完了済みとしてマークするステップ

        Raises:
            RepositoryError: 更新に失敗した場合
        """
        pass

    @abstractmethod
    def is_installation_completed(self) -> bool:
        """インストールが完了しているかどうかを確認する。

        Returns:
            インストールが完了している場合はTrue、そうでなければFalse

        Raises:
            RepositoryError: 確認に失敗した場合
        """
        pass

    @abstractmethod
    def is_camera_permission_dialog_shown(self) -> bool:
        """カメラ許可ダイアログが表示済みかどうかを確認する。

        Returns:
            表示済みの場合はTrue、そうでなければFalse

        Raises:
            RepositoryError: 確認に失敗した場合
        """
        pass

    @abstractmethod
    def mark_camera_permission_dialog_shown(self) -> None:
        """カメラ許可ダイアログを表示済みとしてマークし、永続化する。

        Raises:
            RepositoryError: 更新に失敗した場合
        """
        pass

    @abstractmethod
    def is_youtube_permission_dialog_shown(self) -> bool:
        """YouTube権限ダイアログが表示済みかどうかを確認する。

        Returns:
            表示済みの場合はTrue、そうでなければFalse

        Raises:
            RepositoryError: 確認に失敗した場合
        """
        pass

    @abstractmethod
    def mark_youtube_permission_dialog_shown(self) -> None:
        """YouTube権限ダイアログを表示済みとしてマークし、永続化する。

        Raises:
            RepositoryError: 更新に失敗した場合
        """
        pass


class RepositoryError(Exception):
    """リポジトリ操作で発生するエラーの基底クラス。"""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        """エラーを初期化する。

        Args:
            message: エラーメッセージ
            cause: 原因となった例外（オプション）
        """
        super().__init__(message)
        self.cause = cause
