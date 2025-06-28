from __future__ import annotations

# ruff: noqa: E402

import sys
import types
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))  # noqa: E402

from splat_replay.infrastructure.adapters.capture_device_checker import (
    CaptureDeviceChecker,
)  # noqa: E402
from splat_replay.shared.config import OBSSettings  # noqa: E402


def test_is_connected_uses_settings(monkeypatch):
    settings = OBSSettings(capture_device_name="Test Device")
    checker = CaptureDeviceChecker(settings)

    monkeypatch.setattr(sys, "platform", "win32")

    class FakeDevice:
        Name = "Test Device"

    class FakeWMI:
        def InstancesOf(self, _):
            return [FakeDevice()]

    fake_win32 = types.SimpleNamespace(GetObject=lambda _: FakeWMI())
    fake_pkg = types.ModuleType("win32com")
    fake_pkg.client = fake_win32
    monkeypatch.setitem(sys.modules, "win32com", fake_pkg)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_win32)

    assert checker.is_connected()
