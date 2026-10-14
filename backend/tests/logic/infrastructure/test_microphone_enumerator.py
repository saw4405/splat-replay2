from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from splat_replay.infrastructure.adapters.audio.microphone_enumerator import (
    MicrophoneEnumerator,
)


def _install_pyaudio(
    monkeypatch: pytest.MonkeyPatch,
    snapshots: list[list[dict[str, object]]],
) -> None:
    responses = iter(snapshots)

    class FakePyAudio:
        def __init__(self) -> None:
            self.devices = next(responses)

        def get_device_count(self) -> int:
            return len(self.devices)

        def get_device_info_by_index(self, index: int) -> dict[str, object]:
            return self.devices[index]

        def terminate(self) -> None:
            return None

    pyaudio = ModuleType("pyaudio")
    setattr(pyaudio, "PyAudio", FakePyAudio)
    monkeypatch.setitem(sys.modules, "pyaudio", pyaudio)


def _install_speech_recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_enumeration() -> list[str]:
        raise AssertionError("macOS enumeration must use PortAudio inputs")

    microphone = type(
        "FakeMicrophone",
        (),
        {"list_microphone_names": staticmethod(unexpected_enumeration)},
    )
    speech_recognition = ModuleType("speech_recognition")
    setattr(speech_recognition, "Microphone", microphone)
    monkeypatch.setitem(sys.modules, "speech_recognition", speech_recognition)


def test_macos_lists_only_input_devices_and_resolves_the_portaudio_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    devices = [
        {"name": "Mac miniのスピーカー", "maxInputChannels": 0},
        {"name": "MGM27IC03", "maxInputChannels": 1},
    ]
    _install_pyaudio(monkeypatch, [devices, devices, devices])
    _install_speech_recognition(monkeypatch)
    monkeypatch.setattr(sys, "platform", "darwin")

    enumerator = MicrophoneEnumerator(MagicMock())

    assert enumerator.list_microphones() == ["MGM27IC03"]
    assert enumerator.find_microphone_index("MGM27IC03") == 1
    assert enumerator.find_microphone_index("Mac miniのスピーカー") is None


def test_macos_retries_empty_enumeration_after_permission_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_pyaudio(
        monkeypatch,
        [[], [{"name": "USB microphone", "maxInputChannels": 1}]],
    )
    monkeypatch.setattr(sys, "platform", "darwin")

    enumerator = MicrophoneEnumerator(MagicMock())

    assert enumerator.list_microphones() == []
    assert enumerator.list_microphones() == ["USB microphone"]


def test_macos_rechecks_devices_after_a_previous_nonempty_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_pyaudio(
        monkeypatch,
        [
            [{"name": "USB microphone", "maxInputChannels": 1}],
            [],
        ],
    )
    monkeypatch.setattr(sys, "platform", "darwin")

    enumerator = MicrophoneEnumerator(MagicMock())

    assert enumerator.list_microphones() == ["USB microphone"]
    assert enumerator.list_microphones() == []


def test_windows_keeps_nonempty_microphone_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    enumerator = MicrophoneEnumerator(MagicMock())
    enumeration_calls = 0

    def list_windows_microphones() -> list[str]:
        nonlocal enumeration_calls
        enumeration_calls += 1
        return ["USB microphone"]

    monkeypatch.setattr(
        enumerator, "_list_windows_microphones", list_windows_microphones
    )

    assert enumerator.list_microphones() == ["USB microphone"]
    assert enumerator.list_microphones() == ["USB microphone"]
    assert enumeration_calls == 1
