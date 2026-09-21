"""通知領域で処理中を待機と誤表示しないことを守る。"""

import multiprocessing

import pytest

from splat_replay.interface.gui.desktop_control import (
    DesktopSignals,
    describe_tray_status,
)


@pytest.mark.parametrize(
    "recording,processing,monitoring,power,icon,text",
    [
        (
            "STOPPED",
            "idle",
            "running",
            "waiting_for_power_on",
            "waiting",
            "待機中",
        ),
        (
            "RECORDING",
            "running",
            "running",
            "armed",
            "recording",
            "録画中／編集・アップロード中",
        ),
        ("PAUSED", "idle", "running", "armed", "recording", "録画一時停止中"),
        (
            "STOPPED",
            "running",
            "running",
            "armed",
            "processing",
            "編集・アップロード中",
        ),
        (
            "STOPPED",
            "cancelling",
            "running",
            "armed",
            "processing",
            "停止処理中",
        ),
        ("STOPPED", "failed", "running", "armed", "attention", "失敗"),
        (
            "STOPPED",
            "idle",
            "running",
            "capture_disconnected",
            "attention",
            "機器未接続",
        ),
        (
            "STOPPED",
            "idle",
            "stopped",
            "stopped",
            "attention",
            "自動録画停止中",
        ),
        ("STOPPED", "idle", "running", "unknown", "starting", "機器確認中"),
    ],
)
def test_status_priority(
    recording: str,
    processing: str,
    monitoring: str,
    power: str,
    icon: str,
    text: str,
) -> None:
    actual_icon, actual_text = describe_tray_status(
        recording, processing, monitoring, power
    )
    assert actual_icon == icon
    assert text in actual_text


def _publish(signals: DesktopSignals) -> None:
    signals.tray_status.value = "recording|録画中".encode("utf-8")


def test_spawned_backend_publishes_status() -> None:
    signals = DesktopSignals()
    process = multiprocessing.get_context("spawn").Process(
        target=_publish, args=(signals,)
    )
    process.start()
    try:
        process.join(10)
        assert process.exitcode == 0
        assert signals.tray_status.value.decode("utf-8") == "recording|録画中"
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
