from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.domain.config import SpeechTranscriberSettings
from splat_replay.infrastructure.adapters.audio import (
    speech_transcriber as module,
)
from splat_replay.infrastructure.adapters.audio.speech_transcriber import (
    SpeechTranscriber,
)
from splat_replay.infrastructure.adapters.audio.integrated_speech_recognition import (
    IntegratedSpeechRecognizer,
)
from splat_replay.infrastructure.adapters.audio.microphone_enumerator import (
    MicrophoneEnumerator,
)


class _LoggerStub:
    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        return None

    def error(self, event: str, **kw: object) -> None:
        return None


class _FailingMicrophone:
    def __init__(self, device_index: int) -> None:
        self.device_index = device_index

    def __enter__(self) -> object:
        raise OSError("microphone unavailable")

    def __exit__(self, *args: object) -> None:
        return None


def test_macos_transcriber_resolves_the_listed_input_without_sr_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    devices = [
        {"name": "Mac miniのスピーカー", "maxInputChannels": 0},
        {"name": "MGM27IC03", "maxInputChannels": 1},
    ]

    class FakePyAudio:
        def get_device_count(self) -> int:
            return len(devices)

        def get_device_info_by_index(self, index: int) -> dict[str, object]:
            return devices[index]

        def terminate(self) -> None:
            return None

    def unexpected_enumeration() -> list[str]:
        raise AssertionError("SpeechRecognition fallback must not run")

    pyaudio = ModuleType("pyaudio")
    setattr(pyaudio, "PyAudio", FakePyAudio)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "pyaudio", pyaudio)
    monkeypatch.setattr(
        module.sr.Microphone,
        "list_microphone_names",
        staticmethod(unexpected_enumeration),
    )

    enumerator = MicrophoneEnumerator(MagicMock())

    assert enumerator.list_microphones() == ["MGM27IC03"]
    assert SpeechTranscriber.find_microphone("MGM27IC03") == 1
    assert SpeechTranscriber.find_microphone("Mac miniのスピーカー") is None


@pytest.mark.asyncio
async def test_wait_until_ready_reports_microphone_open_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SpeechTranscriber,
        "find_microphone",
        staticmethod(lambda device_name: 0),
    )
    monkeypatch.setattr(module.sr, "Microphone", _FailingMicrophone)
    transcriber = SpeechTranscriber(
        SpeechTranscriberSettings(mic_device_name="MiraBox"),
        cast(IntegratedSpeechRecognizer, object()),
        cast(BoundLogger, cast(Any, _LoggerStub())),
    )

    transcriber.start()
    ready = await transcriber.wait_until_ready(0.5)
    transcriber.stop()

    assert ready is False
