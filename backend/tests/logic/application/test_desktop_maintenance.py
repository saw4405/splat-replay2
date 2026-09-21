"""更新予約で録画を失わず、後処理の完了を待つ。"""

from unittest.mock import Mock
import pytest

from splat_replay.application.services.system.desktop_maintenance import (
    DesktopMaintenance,
)
from splat_replay.domain.models.switch_power import SwitchPowerState


def test_update_waits_for_switch_and_queued_work_then_cancel_reopens() -> None:
    recording, processing = Mock(), Mock()
    recording.power_off_count = 1
    processing.power_off_count = 0
    recording.power_status.return_value = SwitchPowerState.ARMED
    processing.is_idle.return_value = True
    requested, ready = Mock(return_value=True), Mock()
    gate = DesktopMaintenance(recording, processing, requested, ready)
    assert not gate.check()  # 更新予約後の次のプレイも録画する。
    recording.power_status.return_value = SwitchPowerState.WAITING_FOR_POWER_ON
    assert not gate.check()  # OFF イベントが後処理へ未到達。
    processing.power_off_count = 1
    processing.is_idle.return_value = False
    assert not gate.check()  # 15 秒猶予やアップロード完了を待つ。
    processing.is_idle.return_value = True
    assert gate.check()
    assert processing.start_edit_upload_uc.maintenance is True
    ready.assert_called_once()
    requested.return_value = False
    assert not gate.check()
    assert processing.start_edit_upload_uc.maintenance is False
    assert not processing.update_pending


def test_unknown_disconnected_and_inflight_request_never_allow_update() -> (
    None
):
    recording, processing = Mock(), Mock()
    recording.power_off_count = processing.power_off_count = 0
    processing.is_idle.return_value = True
    for state in (
        SwitchPowerState.UNKNOWN,
        SwitchPowerState.CAPTURE_DISCONNECTED,
    ):
        recording.power_status.return_value = state
        assert not DesktopMaintenance(
            recording, processing, lambda: True, Mock()
        ).check()
    recording.power_status.return_value = SwitchPowerState.WAITING_FOR_POWER_ON
    assert not DesktopMaintenance(
        recording, processing, lambda: True, Mock(), lambda: False
    ).check()


@pytest.mark.parametrize("state", list(SwitchPowerState))
def test_quit_waits_for_work_but_not_switch_power(
    state: SwitchPowerState,
) -> None:
    recording, processing = Mock(), Mock()
    recording.power_status.return_value = state
    recording.power_off_count = 1
    processing.power_off_count = 0
    processing.is_idle.return_value = True
    safe = Mock(return_value=True)
    gate = DesktopMaintenance(
        recording, processing, lambda: True, Mock(), safe, lambda: True
    )
    assert not gate.check()  # 未消化のOFFイベントを破棄しない。
    processing.power_off_count = 1
    processing.is_idle.return_value = False
    assert not gate.check()
    processing.is_idle.return_value = True
    safe.return_value = False
    assert not gate.check()  # 実録画とAPI実行中は待つ。
    safe.return_value = True
    assert gate.check()
