"""セットアップサービス。"""

from __future__ import annotations

from dataclasses import replace
from collections.abc import Callable

from splat_replay.application.interfaces import (
    LoggerPort,
    RequiredSetupIssue,
    RequiredSetupIssueCachePort,
    RequiredSetupConfigPort,
)
from splat_replay.domain.models import SetupState, SetupStep
from splat_replay.domain.repositories import SetupStateRepository
from splat_replay.application.services.setup.required_setup import (
    RequiredSetupIncompleteError,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
    SystemCheckService,
)


class SetupService:
    """セットアップ全体の制御とステップ管理を行うサービス。"""

    def __init__(
        self,
        repository: SetupStateRepository,
        logger: LoggerPort,
        system_check_service: SystemCheckService,
        config: RequiredSetupConfigPort,
        required_setup_issue_cache: RequiredSetupIssueCachePort,
    ) -> None:
        """サービスを初期化する。

        Args:
            repository: セットアップ状態リポジトリ
            logger: ロガー
        """
        self._repository = repository
        self._logger = logger
        self._system_check_service = system_check_service
        self._config = config
        self._required_setup_issue_cache = required_setup_issue_cache

    def get_required_setup_issues(
        self,
        force_refresh: bool = False,
        *,
        repair_legacy_state: bool = False,
    ) -> list[RequiredSetupIssue]:
        """保存済み設定と必要ソフトを検査し、不足を返す。

        外部バイナリ検査はこのメソッドを呼ぶ側でスレッドへ退避できる。
        キャッシュは状態確認の高頻度呼び出しで重い検査を繰り返さないために使う。
        """
        issues = list(
            self._required_setup_issue_cache.get_or_compute(
                self._evaluate_required_setup_issues,
                force_refresh=force_refresh,
            )
        )
        ordered_issues = sorted(issues, key=self._required_issue_order)
        if not repair_legacy_state or not ordered_issues:
            return ordered_issues

        repaired_issues: list[RequiredSetupIssue] = []

        def repair_status_route() -> bool:
            latest_issues = sorted(
                self._required_setup_issue_cache.get_or_compute(
                    self._evaluate_required_setup_issues
                ),
                key=self._required_issue_order,
            )
            if self._repair_legacy_setup_state(latest_issues):
                repaired_issues.extend(latest_issues)
                return True
            return False

        self._required_setup_issue_cache.run_repair_action(
            repair_status_route, only_once=True
        )
        return repaired_issues or ordered_issues

    @staticmethod
    def _required_issue_order(issue: RequiredSetupIssue) -> tuple[int, int]:
        ordered_steps = SetupStep.get_all_steps()
        try:
            step_order = ordered_steps.index(SetupStep(issue.step))
        except ValueError:
            step_order = len(ordered_steps)
        substep_order = {
            "ffmpeg-download-extract": 0,
            "obs-install": 0,
            "obs-ndi": 1,
            "ndi-runtime": 2,
            "video-capture-device": 3,
            "ndi-settings": 5,
            "websocket-password": 6,
            "tesseract-install": 0,
            "transcription-enable": 0,
            "transcription-mic": 1,
            "transcription-groq": 2,
            "youtube-place-file": 0,
            "youtube-privacy-status": 6,
        }.get(issue.substep_id, 99)
        return step_order, substep_order

    def invalidate_required_setup_issues(self) -> None:
        """保存済み設定または外部ソフトが変わったときに検査結果を破棄する。"""
        self._required_setup_issue_cache.invalidate()

    def _evaluate_required_setup_issues(self) -> list[RequiredSetupIssue]:
        issues: list[RequiredSetupIssue] = []

        self._append_software_issue(
            issues,
            self._system_check_service.check_ffmpeg_installation,
            code="ffmpeg_missing",
            step=SetupStep.FFMPEG_SETUP,
            substep_id="ffmpeg-download-extract",
            message="FFmpeg が利用できません。導入後に再検査してください。",
        )
        obs_installed = self._append_software_issue(
            issues,
            self._system_check_service.check_obs_installation,
            code="obs_missing",
            step=SetupStep.OBS_SETUP,
            substep_id="obs-install",
            message="OBS Studio が見つかりません。インストールしてください。",
        )
        if obs_installed:
            self._append_obs_main_output_issue(issues)
        self._append_software_issue(
            issues,
            self._system_check_service.check_distroav_installation,
            code="distroav_missing",
            step=SetupStep.OBS_SETUP,
            substep_id="obs-ndi",
            message="OBS の DistroAV / obs-ndi プラグインが見つかりません。",
        )
        self._append_software_issue(
            issues,
            self._system_check_service.check_ndi_runtime_installation,
            code="ndi_runtime_missing",
            step=SetupStep.OBS_SETUP,
            substep_id="ndi-runtime",
            message="必要な NDI Runtime が利用できません。",
        )
        self._append_software_issue(
            issues,
            self._system_check_service.check_tesseract_installation,
            code="tesseract_missing",
            step=SetupStep.TESSERACT_SETUP,
            substep_id="tesseract-install",
            message="Tesseract OCR が利用できません。",
        )

        self._append_saved_configuration_issues(
            issues, obs_installed=obs_installed
        )
        self._append_software_issue(
            issues,
            self._system_check_service.check_youtube_credentials,
            code="youtube_client_secret_invalid",
            step=SetupStep.YOUTUBE_SETUP,
            substep_id="youtube-place-file",
            message="有効な YouTube OAuth client_secret.json を配置してください。",
        )
        return issues

    def _append_software_issue(
        self,
        issues: list[RequiredSetupIssue],
        check: Callable[[], SoftwareCheckResult],
        *,
        code: str,
        step: SetupStep,
        substep_id: str,
        message: str,
    ) -> bool:
        try:
            result = check()
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "Required setup check failed",
                check=code,
                error_type=type(exc).__name__,
            )
            result_installed = False
        else:
            result_installed = result.is_installed

        if not result_installed:
            issues.append(
                RequiredSetupIssue(
                    code=code,
                    step=step.value,
                    substep_id=substep_id,
                    message=message,
                )
            )
        return result_installed

    def _append_obs_main_output_issue(
        self, issues: list[RequiredSetupIssue]
    ) -> None:
        try:
            result = self._system_check_service.check_obs_main_output()
            status = result.status
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "Required OBS configuration check failed",
                check="obs_configuration_unverified",
                error_type=type(exc).__name__,
            )
            status = "unverified"

        if status == "enabled":
            return
        if status == "disabled":
            code = "ndi_output_disabled"
            message = "OBS の NDI Main Output が無効です。設定を有効にして保存してください。"
        else:
            code = "obs_configuration_unverified"
            message = "OBS の保存設定を確認できません。使用する OBS 構成を確認してください。"
        issues.append(
            RequiredSetupIssue(
                code=code,
                step=SetupStep.OBS_SETUP.value,
                substep_id="ndi-settings",
                message=message,
            )
        )

    def _append_saved_configuration_issues(
        self, issues: list[RequiredSetupIssue], *, obs_installed: bool
    ) -> None:
        try:
            obs = self._config.get_obs_settings()
            capture_device = self._config.get_capture_device_settings()
            upload = self._config.get_upload_settings()
            speech = self._config.get_speech_transcriber_settings()

            password = obs.websocket_password.get_secret_value()
            if (
                not obs.websocket_host.strip()
                or not 1 <= obs.websocket_port <= 65535
                or not password.strip()
            ):
                issues.append(
                    RequiredSetupIssue(
                        code="obs_websocket_unconfigured",
                        step=SetupStep.OBS_SETUP.value,
                        substep_id="websocket-password",
                        message="OBS WebSocket の接続先と認証情報を保存してください。",
                    )
                )
            if obs_installed:
                self._append_obs_websocket_issue(
                    issues,
                    host=obs.websocket_host,
                    port=obs.websocket_port,
                    password=password,
                )

            device_name = capture_device.name.strip()
            if not device_name or device_name == "Capture Device":
                issues.append(
                    RequiredSetupIssue(
                        code="capture_device_unconfigured",
                        step=SetupStep.OBS_SETUP.value,
                        substep_id="video-capture-device",
                        message="使用するキャプチャデバイス名を保存してください。",
                    )
                )

            if upload.privacy_status not in {"private", "unlisted", "public"}:
                issues.append(
                    RequiredSetupIssue(
                        code="youtube_privacy_invalid",
                        step=SetupStep.YOUTUBE_SETUP.value,
                        substep_id="youtube-privacy-status",
                        message="YouTube 動画の公開範囲を保存してください。",
                    )
                )

            if speech.enabled:
                if not speech.mic_device_name.strip():
                    issues.append(
                        RequiredSetupIssue(
                            code="speech_microphone_unconfigured",
                            step=SetupStep.TRANSCRIPTION_SETUP.value,
                            substep_id="transcription-mic",
                            message="文字起こしで使うマイク名を保存してください。",
                        )
                    )
                if not speech.groq_api_key.get_secret_value().strip():
                    issues.append(
                        RequiredSetupIssue(
                            code="speech_api_key_missing",
                            step=SetupStep.TRANSCRIPTION_SETUP.value,
                            substep_id="transcription-groq",
                            message="文字起こしで使う API キーを保存してください。",
                        )
                    )
                if self._system_check_service.is_flac_required_for_transcription():
                    self._append_software_issue(
                        issues,
                        self._system_check_service.check_flac_installation,
                        code="flac_missing",
                        step=SetupStep.TRANSCRIPTION_SETUP,
                        substep_id="transcription-enable",
                        message="文字起こしに必要な FLAC が利用できません。",
                    )
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "Required saved configuration check failed",
                error_type=type(exc).__name__,
            )
            issues.append(
                RequiredSetupIssue(
                    code="saved_configuration_unreadable",
                    step=SetupStep.OBS_SETUP.value,
                    substep_id="websocket-password",
                    message="必須設定を読み取れません。設定を確認して保存してください。",
                )
            )

    def _append_obs_websocket_issue(
        self,
        issues: list[RequiredSetupIssue],
        *,
        host: str,
        port: int,
        password: str,
    ) -> None:
        try:
            status = (
                self._system_check_service.check_obs_websocket_configuration(
                    host, port, password
                ).status
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "Required OBS WebSocket configuration check failed",
                error_type=type(exc).__name__,
            )
            status = "unverified"

        issue_details = {
            "disabled": (
                "obs_websocket_server_disabled",
                "OBS WebSocket サーバーが無効です。OBS の WebSocket 設定で有効にしてください。",
            ),
            "port_mismatch": (
                "obs_websocket_port_mismatch",
                "OBS WebSocket の待受ポートと保存した接続ポートが一致しません。",
            ),
            "password_mismatch": (
                "obs_websocket_password_mismatch",
                "OBS WebSocket の認証パスワードと保存した値が一致しません。",
            ),
            "unverified": (
                "obs_websocket_configuration_unverified",
                "OBS WebSocket の保存設定を確認できません。OBS を一度起動し、WebSocket 設定を保存してから再検査してください。",
            ),
        }.get(status)
        if issue_details is None:
            return
        code, message = issue_details
        issues.append(
            RequiredSetupIssue(
                code=code,
                step=SetupStep.OBS_SETUP.value,
                substep_id="websocket-password",
                message=message,
            )
        )

    def _repair_legacy_setup_state(
        self, issues: list[RequiredSetupIssue]
    ) -> bool:
        if not issues:
            return False
        state = self._repository.load_installation_state()
        if not state.is_completed:
            return False
        first_missing_step = SetupStep(issues[0].step)
        self._repository.save_installation_state(
            replace(state, current_step=first_missing_step)
        )
        return True

    def select_required_setup_issue(self, code: str) -> RequiredSetupIssue:
        """保存済み不足一覧からcanonical修復先を選び、current stepだけ更新する。"""
        selected: list[RequiredSetupIssue] = []

        def select_and_save() -> bool:
            current_issues = sorted(
                self._required_setup_issue_cache.get_or_compute(
                    self._evaluate_required_setup_issues,
                    force_refresh=True,
                ),
                key=self._required_issue_order,
            )
            issue = next(
                (
                    candidate
                    for candidate in current_issues
                    if candidate.code == code
                ),
                None,
            )
            if issue is None:
                raise ValueError("選択した必須設定は現在不足していません。")

            state = self._repository.load_installation_state()
            self._repository.save_installation_state(
                replace(state, current_step=SetupStep(issue.step))
            )
            selected.append(issue)
            return True

        self._required_setup_issue_cache.run_repair_action(
            select_and_save, only_once=False
        )
        return selected[0]

    def check_installation_status(self) -> SetupState:
        """セットアップ状態を確認する。

        Returns:
            現在のセットアップ状態
        """
        self._logger.info("Checking setup status")
        state = self._repository.load_installation_state()

        self._logger.info(
            "Setup status checked",
            is_completed=state.is_completed,
            current_step=state.current_step.value,
            progress=state.get_progress_percentage(),
        )

        return state

    def start_installation(self) -> SetupState:
        """セットアップを開始する。

        Returns:
            初期化されたセットアップ状態
        """
        self._logger.info("Starting setup")

        # 新しいセットアップ状態を作成
        state = SetupState()
        self._repository.save_installation_state(state)
        self.invalidate_required_setup_issues()

        self._logger.info(
            "Setup started",
            current_step=state.current_step.value,
        )

        return state

    def complete_installation(self) -> SetupState:
        """セットアップを完了状態にする。

        Returns:
            完了状態のセットアップ状態
        """
        self._logger.info("Completing setup")

        issues = self.get_required_setup_issues(force_refresh=True)
        if issues:
            raise RequiredSetupIncompleteError(issues)

        state = self._repository.load_installation_state()
        if not state.is_completed:
            state = state.complete_installation()
        self._repository.save_installation_state(state)

        self._logger.info(
            "Setup completed",
            installation_date=state.installation_date,
        )

        return state

    def get_current_step(self) -> SetupStep:
        """現在のセットアップステップを取得する。

        Returns:
            現在のステップ
        """
        state = self._repository.load_installation_state()
        return state.current_step

    def proceed_to_next_step(self) -> SetupState:
        """次のステップに進む。

        Returns:
            更新されたセットアップ状態

        Raises:
            ValueError: 次のステップに進めない場合
        """
        self._logger.info("Proceeding to next step")

        state = self._repository.load_installation_state()
        current_step = state.current_step

        # 最後のステップかどうかを確認
        next_step = current_step.get_next_step()
        is_last_step = next_step is None

        # 最終ステップでは必須設定を再検査し、不足がなければ導入履歴を完了にする。
        if is_last_step:
            issues = self.get_required_setup_issues(force_refresh=True)
            if issues:
                raise RequiredSetupIncompleteError(issues)
            self._logger.info(
                "Last step reached, completing setup",
                current_step=current_step.value,
                is_step_completed=state.is_step_completed(current_step),
            )
            if not state.is_completed:
                state = state.complete_installation()
            self._repository.save_installation_state(state)

            self._logger.info(
                "Setup completed from last step",
                from_step=current_step.value,
                is_completed=state.is_completed,
            )

            return state

        # 最後のステップでない場合は、通常の進行チェックを行う
        if not state.can_proceed_to_next_step():
            # 画面内チェックの完了状態と、必須設定の充足判定は分けて管理する。
            if state.current_step == SetupStep.YOUTUBE_SETUP:
                self._logger.info(
                    "Auto-completing YouTube setup step to finish setup"
                )
                state = state.mark_step_completed(state.current_step)
                self._repository.save_installation_state(state)
            else:
                error_msg = (
                    f"Cannot proceed to next step. "
                    f"Current step '{state.current_step.value}' is not completed or skipped."
                )
                self._logger.error(error_msg)
                raise ValueError(error_msg)

        success, state = state.proceed_to_next_step()

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

    def go_back_to_previous_step(self) -> SetupState:
        """前のステップに戻る。

        Returns:
            更新されたセットアップ状態

        Raises:
            ValueError: 前のステップに戻れない場合
        """
        self._logger.info("Going back to previous step")

        state = self._repository.load_installation_state()
        current_step = state.current_step

        success, state = state.go_back_to_previous_step()

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

    def skip_current_step(self) -> SetupState:
        """現在のステップをスキップする。

        Returns:
            更新されたセットアップ状態
        """
        self._logger.info("Skipping current step")

        state = self._repository.load_installation_state()
        current_step = state.current_step

        # 現在のステップをスキップ済みとしてマーク
        state = state.mark_step_skipped(current_step)
        self._repository.save_installation_state(state)

        self._logger.info(
            "Step skipped",
            step=current_step.value,
            step_display_name=current_step.get_display_name(),
        )

        return state

    def mark_step_completed(self, step: SetupStep) -> SetupState:
        """指定されたステップを完了済みとしてマークする。

        Args:
            step: 完了済みとしてマークするステップ

        Returns:
            更新されたセットアップ状態
        """
        self._logger.info(
            "Marking step as completed",
            step=step.value,
            step_display_name=step.get_display_name(),
        )

        state = self._repository.load_installation_state()
        state = state.mark_step_completed(step)
        self._repository.save_installation_state(state)

        self._logger.info(
            "Step marked as completed",
            step=step.value,
            progress=state.get_progress_percentage(),
        )

        return state

    def mark_substep_completed(
        self, step: SetupStep, substep_id: str, completed: bool = True
    ) -> SetupState:
        """指定されたサブステップを完了済みとしてマークする。

        Args:
            step: ステップ
            substep_id: サブステップID
            completed: 完了状態

        Returns:
            更新されたセットアップ状態
        """
        self._logger.info(
            "Marking substep as completed",
            step=step.value,
            substep_id=substep_id,
            completed=completed,
        )

        state = self._repository.load_installation_state()
        state = state.mark_substep_completed(step, substep_id, completed)
        self._repository.save_installation_state(state)

        return state

    def is_installation_completed(self) -> bool:
        """履歴と現在の必須設定が両方そろっているか確認する。

        Returns:
            セットアップが完了している場合はTrue、そうでなければFalse
        """
        return self._repository.is_installation_completed() and not (
            self.get_required_setup_issues()
        )

    def get_progress_percentage(self) -> float:
        """セットアップ進行状況をパーセンテージで取得する。

        Returns:
            進行状況のパーセンテージ（0.0〜100.0）
        """
        state = self._repository.load_installation_state()
        return state.get_progress_percentage()

    def get_remaining_steps(self) -> list[SetupStep]:
        """残りのステップリストを取得する。

        Returns:
            残りのステップのリスト
        """
        state = self._repository.load_installation_state()
        return state.get_remaining_steps()

    def reset_installation(self) -> SetupState:
        """セットアップ状態をリセットする。

        Returns:
            リセットされたセットアップ状態
        """
        self._logger.warning("Resetting setup state")

        state = SetupState()
        self._repository.save_installation_state(state)
        self.invalidate_required_setup_issues()

        self._logger.info("Setup state reset")

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
