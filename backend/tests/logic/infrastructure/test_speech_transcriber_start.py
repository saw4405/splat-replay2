from __future__ import annotations

from typing import Any, cast

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
