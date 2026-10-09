from __future__ import annotations

import multiprocessing
import os
import runpy
import sys

import pytest


@pytest.mark.parametrize(
    ("platform", "frozen"),
    [("darwin", True), ("win32", False)],
)
def test_packaged_entrypoint_handles_spawn_worker_before_gui_import(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    frozen: bool,
) -> None:
    class FreezeSupportCalled(Exception):
        pass

    def stop_at_freeze_support() -> None:
        raise FreezeSupportCalled

    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(
        multiprocessing, "freeze_support", stop_at_freeze_support
    )

    with pytest.raises(FreezeSupportCalled):
        runpy.run_module("splat_replay.bootstrap.webview", run_name="__main__")


def test_frozen_macos_app_prefers_homebrew_without_changing_shell_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FreezeSupportCalled(Exception):
        pass

    def stop_at_freeze_support() -> None:
        raise FreezeSupportCalled

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        multiprocessing,
        "freeze_support",
        stop_at_freeze_support,
    )
    monkeypatch.setenv(
        "PATH", "/usr/bin:/opt/homebrew/bin:/custom:/opt/homebrew/bin"
    )

    with pytest.raises(FreezeSupportCalled):
        runpy.run_module("splat_replay.bootstrap.webview", run_name="__main__")

    assert os.environ["PATH"] == "/opt/homebrew/bin:/usr/bin:/custom"
