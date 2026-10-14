"""必須セットアップ判定のロジック回帰。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from pydantic import SecretStr
import pytest

from splat_replay.application.interfaces import (
    LoggerPort,
    OBSMainOutputCheckResult,
    OBSWebSocketCheckResult,
    OBSWebSocketStatus,
    RequiredSetupConfigPort,
)
from splat_replay.application.services.setup.setup_service import SetupService
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
    SystemCheckService,
)
from splat_replay.domain.models import SetupState, SetupStep
from splat_replay.domain.repositories import SetupStateRepository
from splat_replay.infrastructure.adapters.system.required_setup_issue_cache import (
    InMemoryRequiredSetupIssueCache,
)


class MemorySetupRepository(SetupStateRepository):
    def __init__(self, state: SetupState) -> None:
        self.state = state

    def save_installation_state(self, state: SetupState) -> None:
        self.state = state

    def load_installation_state(self) -> SetupState:
        return self.state

    def mark_step_completed(self, step: SetupStep) -> None:
        self.state = self.state.mark_step_completed(step)

    def is_installation_completed(self) -> bool:
        return self.state.is_completed

    def is_camera_permission_dialog_shown(self) -> bool:
        return self.state.camera_permission_dialog_shown

    def mark_camera_permission_dialog_shown(self) -> None:
        self.state = replace(self.state, camera_permission_dialog_shown=True)

    def is_youtube_permission_dialog_shown(self) -> bool:
        return self.state.youtube_permission_dialog_shown

    def mark_youtube_permission_dialog_shown(self) -> None:
        self.state = replace(self.state, youtube_permission_dialog_shown=True)


def make_service(
    state: SetupState | None = None,
) -> tuple[SetupService, MemorySetupRepository, MagicMock, MagicMock]:
    repository = MemorySetupRepository(state or SetupState())
    checks = MagicMock(spec=SystemCheckService)
    for method_name in (
        "check_ffmpeg_installation",
        "check_obs_installation",
        "check_distroav_installation",
        "check_ndi_runtime_installation",
        "check_obs_main_output",
        "check_obs_websocket_configuration",
        "check_tesseract_installation",
        "check_font_installation",
        "check_flac_installation",
        "check_youtube_credentials",
    ):
        getattr(checks, method_name).return_value = SoftwareCheckResult(
            is_installed=True
        )
    checks.is_flac_required_for_transcription.return_value = False
    checks.check_obs_main_output.return_value = OBSMainOutputCheckResult(
        status="enabled"
    )
    checks.check_obs_websocket_configuration.return_value = (
        OBSWebSocketCheckResult(status="ready")
    )

    config = MagicMock(spec=RequiredSetupConfigPort)
    config.get_obs_settings.return_value = SimpleNamespace(
        websocket_host="127.0.0.1",
        websocket_port=4455,
        websocket_password=SecretStr("saved-password"),
    )
    config.get_capture_device_settings.return_value = SimpleNamespace(
        name="OBS Virtual Camera"
    )
    config.get_upload_settings.return_value = SimpleNamespace(
        privacy_status="private"
    )
    config.get_speech_transcriber_settings.return_value = SimpleNamespace(
        enabled=False,
        mic_device_name="",
        groq_api_key=SecretStr(""),
    )

    service = SetupService(
        repository=repository,
        logger=MagicMock(spec=LoggerPort),
        system_check_service=checks,
        config=config,
        required_setup_issue_cache=InMemoryRequiredSetupIssueCache(),
    )
    return service, repository, checks, config


def test_optional_transcription_does_not_require_microphone_api_key_or_flac() -> (
    None
):
    service, _, checks, _ = make_service()

    assert service.get_required_setup_issues(force_refresh=True) == []
    checks.check_flac_installation.assert_not_called()


def test_disabled_ndi_main_output_routes_to_saved_settings_card() -> None:
    service, _, checks, _ = make_service()
    checks.check_obs_main_output.return_value = OBSMainOutputCheckResult(
        status="disabled"
    )

    issues = service.get_required_setup_issues(force_refresh=True)

    issue = next(
        issue for issue in issues if issue.code == "ndi_output_disabled"
    )
    assert issue.step == SetupStep.OBS_SETUP.value
    assert issue.substep_id == "ndi-settings"
    assert "無効" in issue.message


def test_unverified_ndi_configuration_blocks_without_claiming_disabled() -> (
    None
):
    service, _, checks, _ = make_service()
    checks.check_obs_main_output.return_value = OBSMainOutputCheckResult(
        status="unverified"
    )

    issues = service.get_required_setup_issues(force_refresh=True)

    issue = next(
        issue
        for issue in issues
        if issue.code == "obs_configuration_unverified"
    )
    assert issue.step == SetupStep.OBS_SETUP.value
    assert issue.substep_id == "ndi-settings"
    assert "確認できません" in issue.message


@pytest.mark.parametrize(
    ("status", "issue_code"),
    [
        ("ready", None),
        ("disabled", "obs_websocket_server_disabled"),
        ("port_mismatch", "obs_websocket_port_mismatch"),
        ("password_mismatch", "obs_websocket_password_mismatch"),
        (
            "unverified",
            "obs_websocket_configuration_unverified",
        ),
        ("not_applicable", None),
    ],
)
def test_obs_websocket_status_routes_only_local_configuration_gaps_to_password_card(
    status: OBSWebSocketStatus, issue_code: str | None
) -> None:
    service, _, checks, _ = make_service()
    secret = "saved-password"
    checks.check_obs_websocket_configuration.return_value = (
        OBSWebSocketCheckResult(status=status)
    )

    issues = service.get_required_setup_issues(force_refresh=True)

    assert secret not in repr(issues)
    websocket_issues = [
        issue
        for issue in issues
        if issue.substep_id == "websocket-password"
        and issue.code != "obs_websocket_unconfigured"
    ]
    if issue_code is None:
        assert websocket_issues == []
    else:
        assert [issue.code for issue in websocket_issues] == [issue_code]
        assert all(
            issue.step == SetupStep.OBS_SETUP.value
            for issue in websocket_issues
        )
        if status == "unverified":
            assert all(
                expected in websocket_issues[0].message
                for expected in ("OBS を一度起動", "保存", "再検査")
            )
    checks.check_obs_websocket_configuration.assert_called_once_with(
        "127.0.0.1", 4455, "saved-password"
    )


def test_remote_obs_websocket_configuration_is_not_a_local_requirement() -> (
    None
):
    service, _, checks, config = make_service()
    config.get_obs_settings.return_value = SimpleNamespace(
        websocket_host="192.0.2.10",
        websocket_port=4455,
        websocket_password=SecretStr("saved-password"),
    )
    checks.check_obs_websocket_configuration.return_value = (
        OBSWebSocketCheckResult(status="not_applicable")
    )

    issues = service.get_required_setup_issues(force_refresh=True)

    assert not any("websocket" in issue.code for issue in issues)


def test_ndi_configuration_is_not_checked_when_obs_is_missing() -> None:
    service, _, checks, _ = make_service()
    checks.check_obs_installation.return_value = SoftwareCheckResult(
        is_installed=False
    )

    issues = service.get_required_setup_issues(force_refresh=True)

    assert "obs_missing" in {issue.code for issue in issues}
    assert "obs_configuration_unverified" not in {
        issue.code for issue in issues
    }
    checks.check_obs_main_output.assert_not_called()
    checks.check_obs_websocket_configuration.assert_not_called()


def test_enabled_transcription_requires_saved_inputs_and_macos_flac() -> None:
    service, _, checks, config = make_service()
    config.get_speech_transcriber_settings.return_value = SimpleNamespace(
        enabled=True,
        mic_device_name=" ",
        groq_api_key=SecretStr(""),
    )
    checks.is_flac_required_for_transcription.return_value = True
    checks.check_flac_installation.return_value = SoftwareCheckResult(
        is_installed=False
    )

    issues = service.get_required_setup_issues(force_refresh=True)

    assert [issue.code for issue in issues] == [
        "flac_missing",
        "speech_microphone_unconfigured",
        "speech_api_key_missing",
    ]
    assert issues[0].substep_id == "transcription-enable"
    checks.check_flac_installation.assert_called_once()


def test_legacy_repair_routes_once_and_preserves_installation_history() -> (
    None
):
    installation_date = datetime(2024, 1, 2, 3, 4, 5)
    initial_state = SetupState(
        is_completed=True,
        current_step=SetupStep.YOUTUBE_SETUP,
        completed_steps=(SetupStep.FFMPEG_SETUP, SetupStep.OBS_SETUP),
        skipped_steps=(SetupStep.HARDWARE_CHECK,),
        step_details={"obs_setup": {"obs-install": True}},
        installation_date=installation_date,
    )
    service, repository, checks, _ = make_service(initial_state)
    checks.check_ffmpeg_installation.return_value = SoftwareCheckResult(
        is_installed=False
    )

    assert service.is_installation_completed() is False
    assert repository.state.current_step is SetupStep.YOUTUBE_SETUP

    issues = service.get_required_setup_issues(repair_legacy_state=True)
    assert issues[0].code == "ffmpeg_missing"
    repaired_state = repository.state
    assert repaired_state.current_step is SetupStep.FFMPEG_SETUP
    assert repaired_state.is_completed is True
    assert repaired_state.installation_date == installation_date
    assert repaired_state.completed_steps == initial_state.completed_steps
    assert repaired_state.skipped_steps == initial_state.skipped_steps
    assert repaired_state.step_details == initial_state.step_details

    repository.save_installation_state(
        replace(repository.state, current_step=SetupStep.YOUTUBE_SETUP)
    )
    service.get_required_setup_issues(repair_legacy_state=True)
    assert repository.state.current_step is SetupStep.YOUTUBE_SETUP

    checks.check_ffmpeg_installation.return_value = SoftwareCheckResult(
        is_installed=True
    )
    service.invalidate_required_setup_issues()
    completed_state = service.complete_installation()
    assert completed_state.installation_date == installation_date


def test_explicit_repair_selection_can_choose_later_issue_without_rewind() -> (
    None
):
    installation_date = datetime(2024, 1, 2, 3, 4, 5)
    initial_state = SetupState(
        is_completed=True,
        current_step=SetupStep.YOUTUBE_SETUP,
        completed_steps=(SetupStep.FFMPEG_SETUP, SetupStep.OBS_SETUP),
        skipped_steps=(SetupStep.HARDWARE_CHECK,),
        step_details={"obs_setup": {"obs-install": True}},
        installation_date=installation_date,
    )
    service, repository, checks, _ = make_service(initial_state)
    checks.check_ffmpeg_installation.return_value = SoftwareCheckResult(
        is_installed=False
    )
    checks.check_obs_installation.return_value = SoftwareCheckResult(
        is_installed=False
    )

    selected = service.select_required_setup_issue("obs_missing")

    assert selected.code == "obs_missing"
    assert selected.step == SetupStep.OBS_SETUP.value
    assert repository.state.current_step is SetupStep.OBS_SETUP
    assert repository.state.is_completed is True
    assert repository.state.installation_date == installation_date
    assert repository.state.completed_steps == initial_state.completed_steps
    assert repository.state.skipped_steps == initial_state.skipped_steps
    assert repository.state.step_details == initial_state.step_details

    # The initial legacy repair route must not override an explicit target.
    service.get_required_setup_issues(repair_legacy_state=True)
    assert repository.state.current_step is SetupStep.OBS_SETUP
