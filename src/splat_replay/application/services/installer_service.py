"""インストーラーサービス。"""

from __future__ import annotations

from structlog.stdlib import BoundLogger

from splat_replay.domain.models import InstallationState, InstallationStep
from splat_replay.domain.repositories import InstallationStateRepository


class InstallerService:
    """インストーラー全体の制御とステップ管理を行うサービス。"""

    def __init__(
        self,
        repository: InstallationStateRepository,
        logger: BoundLogger,
    ) -> None:
        """サービスを初期化する。

        Args:
            repository: インストール状態リポジトリ
            logger: ロガー
        """
        self._repository = repository
        self._logger = logger

    def check_installation_status(self) -> InstallationState:
        """インストール状態を確認する。

        Returns:
            現在のインストール状態
        """
        self._logger.info("Checking installation status")
        state = self._repository.load_installation_state()

        self._logger.info(
            "Installation status checked",
            is_completed=state.is_completed,
            current_step=state.current_step.value,
            progress=state.get_progress_percentage(),
        )

        return state

    def start_installation(self) -> InstallationState:
        """インストーラーを開始する。

        Returns:
            初期化されたインストール状態
        """
        self._logger.info("Starting installation")

        # 新しいインストール状態を作成
        state = InstallationState()
        self._repository.save_installation_state(state)

        self._logger.info(
            "Installation started",
            current_step=state.current_step.value,
        )

        return state

    def complete_installation(self) -> InstallationState:
        """インストールを完了状態にする。

        Returns:
            完了状態のインストール状態
        """
        self._logger.info("Completing installation")

        state = self._repository.load_installation_state()
        state.complete_installation()
        self._repository.save_installation_state(state)

        self._logger.info(
            "Installation completed",
            installation_date=state.installation_date,
        )

        return state

    def get_current_step(self) -> InstallationStep:
        """現在のインストールステップを取得する。

        Returns:
            現在のステップ
        """
        state = self._repository.load_installation_state()
        return state.current_step

    def proceed_to_next_step(self) -> InstallationState:
        """次のステップに進む。

        Returns:
            更新されたインストール状態

        Raises:
            ValueError: 次のステップに進めない場合
        """
        self._logger.info("Proceeding to next step")

        state = self._repository.load_installation_state()
        current_step = state.current_step

        # 最後のステップかどうかを確認
        next_step = current_step.get_next_step()
        is_last_step = next_step is None

        # 最後のステップの場合、完了していなくてもインストールを完了とする
        if is_last_step:
            self._logger.info(
                "Last step reached, completing installation",
                current_step=current_step.value,
                is_step_completed=state.is_step_completed(current_step),
            )
            state.complete_installation()
            self._repository.save_installation_state(state)

            self._logger.info(
                "Installation completed from last step",
                from_step=current_step.value,
                is_completed=state.is_completed,
            )

            return state

        # 最後のステップでない場合は、通常の進行チェックを行う
        if not state.can_proceed_to_next_step():
            # YouTubeセットアップは最後のステップであり、部分的な設定でも完了とみなして進めるようにする
            # (ユーザーからの「制限をつけないで」という要望への対応)
            if state.current_step == InstallationStep.YOUTUBE_SETUP:
                self._logger.info(
                    "Auto-completing YouTube setup step to finish installation"
                )
                state.mark_step_completed(state.current_step)
                self._repository.save_installation_state(state)
            else:
                error_msg = (
                    f"Cannot proceed to next step. "
                    f"Current step '{state.current_step.value}' is not completed or skipped."
                )
                self._logger.error(error_msg)
                raise ValueError(error_msg)

        success = state.proceed_to_next_step()

        if not success:
            error_msg = "Failed to proceed to next step"
            self._logger.error(error_msg)
            raise ValueError(error_msg)

        self._repository.save_installation_state(state)

        self._logger.info(
            "Proceeded to next step",
            from_step=current_step.value,
            to_step=state.current_step.value
            if not state.is_completed
            else "completed",
            is_completed=state.is_completed,
        )

        return state

    def go_back_to_previous_step(self) -> InstallationState:
        """前のステップに戻る。

        Returns:
            更新されたインストール状態

        Raises:
            ValueError: 前のステップに戻れない場合
        """
        self._logger.info("Going back to previous step")

        state = self._repository.load_installation_state()
        current_step = state.current_step

        success = state.go_back_to_previous_step()

        if not success:
            error_msg = "Cannot go back. Already at the first step."
            self._logger.error(error_msg)
            raise ValueError(error_msg)

        self._repository.save_installation_state(state)

        self._logger.info(
            "Went back to previous step",
            from_step=current_step.value,
            to_step=state.current_step.value,
        )

        return state

    def skip_current_step(self) -> InstallationState:
        """現在のステップをスキップする。

        Returns:
            更新されたインストール状態
        """
        self._logger.info("Skipping current step")

        state = self._repository.load_installation_state()
        current_step = state.current_step

        # 現在のステップをスキップ済みとしてマーク
        state.mark_step_skipped(current_step)
        self._repository.save_installation_state(state)

        self._logger.info(
            "Step skipped",
            step=current_step.value,
            step_display_name=current_step.get_display_name(),
        )

        return state

    def mark_step_completed(self, step: InstallationStep) -> InstallationState:
        """指定されたステップを完了済みとしてマークする。

        Args:
            step: 完了済みとしてマークするステップ

        Returns:
            更新されたインストール状態
        """
        self._logger.info(
            "Marking step as completed",
            step=step.value,
            step_display_name=step.get_display_name(),
        )

        state = self._repository.load_installation_state()
        state.mark_step_completed(step)
        self._repository.save_installation_state(state)

        self._logger.info(
            "Step marked as completed",
            step=step.value,
            progress=state.get_progress_percentage(),
        )

        return state

    def mark_substep_completed(
        self, step: InstallationStep, substep_id: str, completed: bool = True
    ) -> InstallationState:
        """指定されたサブステップを完了済みとしてマークする。

        Args:
            step: ステップ
            substep_id: サブステップID
            completed: 完了状態

        Returns:
            更新されたインストール状態
        """
        self._logger.info(
            "Marking substep as completed",
            step=step.value,
            substep_id=substep_id,
            completed=completed,
        )

        state = self._repository.load_installation_state()
        state.mark_substep_completed(step, substep_id, completed)
        self._repository.save_installation_state(state)

        return state

    def is_installation_completed(self) -> bool:
        """インストールが完了しているかどうかを確認する。

        Returns:
            インストールが完了している場合はTrue、そうでなければFalse
        """
        return self._repository.is_installation_completed()

    def get_progress_percentage(self) -> float:
        """インストール進行状況をパーセンテージで取得する。

        Returns:
            進行状況のパーセンテージ（0.0〜100.0）
        """
        state = self._repository.load_installation_state()
        return state.get_progress_percentage()

    def get_remaining_steps(self) -> list[InstallationStep]:
        """残りのステップリストを取得する。

        Returns:
            残りのステップのリスト
        """
        state = self._repository.load_installation_state()
        return state.get_remaining_steps()

    def reset_installation(self) -> InstallationState:
        """インストール状態をリセットする。

        Returns:
            リセットされたインストール状態
        """
        self._logger.warning("Resetting installation state")

        state = InstallationState()
        self._repository.save_installation_state(state)

        self._logger.info("Installation state reset")

        return state

    def is_camera_permission_dialog_shown(self) -> bool:
        """カメラ許可ダイアログが表示済みかどうかを確認する。

        Returns:
            表示済みの場合はTrue、そうでなければFalse
        """
        return self._repository.is_camera_permission_dialog_shown()

    def mark_camera_permission_dialog_shown(self) -> None:
        """カメラ許可ダイアログを表示済みとしてマークする。"""
        self._logger.info("Marking camera permission dialog as shown")
        self._repository.mark_camera_permission_dialog_shown()
        self._logger.info("Camera permission dialog marked as shown")

    def is_youtube_permission_dialog_shown(self) -> bool:
        """YouTube権限ダイアログが表示済みかどうかを確認する。

        Returns:
            表示済みの場合はTrue、そうでなければFalse
        """
        return self._repository.is_youtube_permission_dialog_shown()

    def mark_youtube_permission_dialog_shown(self) -> None:
        """YouTube権限ダイアログを表示済みとしてマークする。"""
        self._logger.info("Marking youtube permission dialog as shown")
        self._repository.mark_youtube_permission_dialog_shown()
        self._logger.info("YouTube permission dialog marked as shown")
