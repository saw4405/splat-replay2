from __future__ import annotations

import pytest

from splat_replay.domain.models import SwitchPowerMonitor, SwitchPowerState


def _observe(
    monitor: SwitchPowerMonitor, power_is_off: bool, count: int
) -> tuple[SwitchPowerMonitor, list[bool]]:
    requests: list[bool] = []
    for _ in range(count):
        monitor, requested = monitor.observe(power_is_off=power_is_off)
        requests.append(requested)
    return monitor, requests


def test_startup_off_waits_without_requesting_post_process() -> None:
    monitor, requests = _observe(SwitchPowerMonitor(), True, 3)

    assert monitor.state is SwitchPowerState.WAITING_FOR_POWER_ON
    assert requests == [False, False, False]


def test_power_cycle_requests_post_process_once_and_rearms() -> None:
    monitor = SwitchPowerMonitor()
    all_requests: list[bool] = []

    for _ in range(3):
        monitor, requests = _observe(monitor, False, 3)
        all_requests.extend(requests)
        assert monitor.state is SwitchPowerState.ARMED

        monitor, requests = _observe(monitor, True, 3)
        all_requests.extend(requests)
        assert monitor.state is SwitchPowerState.WAITING_FOR_POWER_ON

        monitor, requests = _observe(monitor, True, 6)
        all_requests.extend(requests)
        assert monitor.state is SwitchPowerState.WAITING_FOR_POWER_ON

    assert all_requests.count(True) == 3


def test_single_non_off_observation_does_not_rearm() -> None:
    monitor, _ = _observe(SwitchPowerMonitor(), True, 3)

    monitor, requests = _observe(monitor, False, 1)

    assert monitor.state is SwitchPowerState.WAITING_FOR_POWER_ON
    assert requests == [False]


def test_stopped_monitor_ignores_observations() -> None:
    monitor = SwitchPowerMonitor().stop()

    observed, requested = monitor.observe(power_is_off=False)

    assert observed is monitor
    assert requested is False


def test_capture_disconnect_is_distinct_and_reconnect_rearms() -> None:
    monitor, _ = _observe(SwitchPowerMonitor(), False, 3)

    monitor = monitor.disconnect()

    assert monitor.state is SwitchPowerState.CAPTURE_DISCONNECTED
    monitor, requests = _observe(monitor, False, 3)
    assert monitor.state is SwitchPowerState.ARMED
    assert requests == [False, False, False]


@pytest.mark.parametrize(
    "kwargs",
    [{"off_threshold": 0}, {"on_threshold": 0}],
)
def test_threshold_must_be_positive(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        if "off_threshold" in kwargs:
            SwitchPowerMonitor(off_threshold=kwargs["off_threshold"])
        else:
            SwitchPowerMonitor(on_threshold=kwargs["on_threshold"])
