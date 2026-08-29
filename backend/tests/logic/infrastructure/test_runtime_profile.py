"""実行プロファイルによる DI 構成のテスト。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import cast

import punq
import pytest
from splat_replay.application.interfaces import (
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CapturePort,
    MicrophoneEnumeratorPort,
    OCRPort,
    PowerPort,
    VideoRecorderPort,
    WeaponRecognitionPort,
)
from splat_replay.domain.ports import BattleMedalRecognizerPort
from splat_replay.infrastructure.adapters.capture.adaptive_capture import (
    AdaptiveCapture,
)
from splat_replay.infrastructure.adapters.capture.adaptive_capture_device_checker import (
    AdaptiveCaptureDeviceChecker,
)
from splat_replay.infrastructure.adapters.medal_detection.replay_recognizer import (
    ReplayBattleMedalRecognizerAdapter,
)
from splat_replay.infrastructure.adapters.system.replay_runtime import (
    ReplayCaptureDeviceEnumerator,
    ReplayMicrophoneEnumerator,
    ReplayPower,
)
from splat_replay.infrastructure.adapters.text.replay_ocr import (
    ReplayOCRAdapter,
)
from splat_replay.infrastructure.adapters.video.adaptive_video_recorder import (
    AdaptiveVideoRecorder,
)
from splat_replay.infrastructure.adapters.weapon_detection.replay_recognizer import (
    ReplayWeaponRecognitionAdapter,
)
from splat_replay.infrastructure.di import configure_container, resolve
from splat_replay.infrastructure.di.runtime_profile import (
    RUNTIME_PROFILE_ENV,
    RuntimeProfile,
    resolve_runtime_profile,
)
from splat_replay.infrastructure.filesystem import paths


def _configure_replay_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "config" / "settings.toml"
    replay_video = tmp_path / "replay.mkv"
    replay_video.write_bytes(b"replay input")
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("[storage]\n", encoding="utf-8")
    (settings_path.parent / "e2e-replay-input.json").write_text(
        json.dumps({"video_path": str(replay_video)}), encoding="utf-8"
    )
    monkeypatch.setenv("SPLAT_REPLAY_SETTINGS_FILE", str(settings_path))
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)


def test_runtime_profile_defaults_to_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(RUNTIME_PROFILE_ENV, raising=False)

    assert resolve_runtime_profile() is RuntimeProfile.LIVE


def test_runtime_profile_accepts_replay_value() -> None:
    assert resolve_runtime_profile(" RePlAy ") is RuntimeProfile.REPLAY


def test_runtime_profile_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match=RUNTIME_PROFILE_ENV):
        resolve_runtime_profile("preview")


def test_live_profile_resolves_adaptive_adapters() -> None:
    container = configure_container(profile=RuntimeProfile.LIVE)

    assert isinstance(resolve(container, CapturePort), AdaptiveCapture)
    assert isinstance(
        resolve(container, CaptureDevicePort), AdaptiveCaptureDeviceChecker
    )
    assert isinstance(
        resolve(container, VideoRecorderPort), AdaptiveVideoRecorder
    )


def test_replay_profile_registers_only_replay_device_adapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_replay_input(tmp_path, monkeypatch)

    container = configure_container(profile=RuntimeProfile.REPLAY)

    assert isinstance(resolve(container, CapturePort), AdaptiveCapture)
    assert isinstance(
        resolve(container, CaptureDevicePort), AdaptiveCaptureDeviceChecker
    )
    assert isinstance(
        resolve(container, VideoRecorderPort), AdaptiveVideoRecorder
    )
    assert isinstance(
        resolve(container, CaptureDeviceEnumeratorPort),
        ReplayCaptureDeviceEnumerator,
    )
    assert isinstance(
        resolve(container, MicrophoneEnumeratorPort),
        ReplayMicrophoneEnumerator,
    )
    assert isinstance(resolve(container, PowerPort), ReplayPower)
    assert isinstance(resolve(container, OCRPort), ReplayOCRAdapter)
    assert isinstance(
        resolve(container, BattleMedalRecognizerPort),
        ReplayBattleMedalRecognizerAdapter,
    )
    assert isinstance(
        resolve(container, WeaponRecognitionPort),
        ReplayWeaponRecognitionAdapter,
    )


@pytest.mark.asyncio
async def test_replay_profile_rejects_power_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_replay_input(tmp_path, monkeypatch)
    container = configure_container(profile=RuntimeProfile.REPLAY)

    with pytest.raises(RuntimeError, match="電源操作"):
        await resolve(container, PowerPort).sleep()


def test_replay_profile_requires_input_before_adapter_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "config" / "settings.toml"
    settings_path.parent.mkdir(parents=True)
    monkeypatch.setenv("SPLAT_REPLAY_SETTINGS_FILE", str(settings_path))
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)

    with pytest.raises(RuntimeError, match="replay 入力"):
        configure_container(profile=RuntimeProfile.REPLAY)


def test_replay_profile_does_not_import_live_native_adapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """replay の Composition Root は live 専用 native 依存へ到達しない。"""
    _configure_replay_input(tmp_path, monkeypatch)
    settings_path = tmp_path / "config" / "settings.toml"
    script = """
import importlib.abc
import sys

BLOCKED_PREFIXES = (
    "cyndilib",
    "pytesseract",
    "splat_replay.infrastructure.adapters.capture.ndi_capture",
    "splat_replay.infrastructure.adapters.obs",
    "splat_replay.infrastructure.adapters.medal_detection.recognizer",
    "splat_replay.infrastructure.adapters.text.tesseract_ocr",
    "splat_replay.infrastructure.adapters.weapon_detection.recognizer",
)


class LiveNativeDependencyBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(
            fullname == prefix or fullname.startswith(f"{prefix}.")
            for prefix in BLOCKED_PREFIXES
        ):
            raise ModuleNotFoundError(f"replay must not import {fullname}")
        return None


sys.meta_path.insert(0, LiveNativeDependencyBlocker())

from splat_replay.application.interfaces import (
    CaptureDevicePort,
    CapturePort,
    VideoRecorderPort,
)
from splat_replay.infrastructure.di import configure_container, resolve
from splat_replay.infrastructure.di.runtime_profile import RuntimeProfile

container = configure_container(profile=RuntimeProfile.REPLAY)
resolve(container, CaptureDevicePort)
resolve(container, CapturePort)
resolve(container, VideoRecorderPort)

assert not any(
    module == prefix or module.startswith(f"{prefix}.")
    for module in sys.modules
    for prefix in BLOCKED_PREFIXES
)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[3],
        env={**os.environ, "SPLAT_REPLAY_SETTINGS_FILE": str(settings_path)},
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_cli_composition_root_resolves_runtime_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI も Web と同じ実行プロファイルを Composition Root へ渡す。"""
    from splat_replay.bootstrap import cli

    captured_profiles: list[RuntimeProfile] = []
    container = cast(punq.Container, object())

    def _configure_container(*, profile: RuntimeProfile) -> punq.Container:
        captured_profiles.append(profile)
        return container

    monkeypatch.setattr(
        cli, "resolve_runtime_profile", lambda: RuntimeProfile.REPLAY
    )
    monkeypatch.setattr(cli, "configure_container", _configure_container)

    resources = cli._LazyResources()

    assert resources.container() is container
    assert captured_profiles == [RuntimeProfile.REPLAY]
