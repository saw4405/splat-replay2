from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import speech_recognition as sr
import pytest
from pydantic import SecretStr
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import SpeechSynthesisRequest
from splat_replay.domain.config import VideoEditSettings
from splat_replay.domain.config.video_edit import SubtitleSpeechSettings
from splat_replay.infrastructure.adapters.audio.google_text_to_speech import (
    GoogleTextToSpeech,
)
from splat_replay.infrastructure.adapters.audio.integrated_speech_recognition import (
    IntegratedSpeechRecognizer,
)


def _logged_fields(logger: MagicMock) -> str:
    return repr(logger.method_calls)


def _audio() -> sr.AudioData:
    return cast(
        sr.AudioData,
        SimpleNamespace(get_wav_data=lambda: b"fake audio payload"),
    )


def test_google_recognition_uses_https_and_does_not_log_provider_error() -> (
    None
):
    logger = MagicMock()
    request_error_marker = "GOOGLE_ERROR_BODY_SENTINEL"
    observed: dict[str, object] = {}

    def recognize_google(
        audio: sr.AudioData, *, language: str, endpoint: str
    ) -> str:
        del audio
        observed.update(language=language, endpoint=endpoint)
        raise sr.RequestError(
            f"https://example.invalid/?key=SHARED_KEY_SENTINEL {request_error_marker}"
        )

    recognizer = object.__new__(IntegratedSpeechRecognizer)
    recognizer._recognizer = cast(
        Any, SimpleNamespace(recognize_google=recognize_google)
    )
    recognizer._logger = cast(BoundLogger, logger)
    audio = _audio()

    result = asyncio.run(recognizer.recognize_google(audio, "ja-JP"))

    assert result is None
    assert observed == {
        "language": "ja-JP",
        "endpoint": "https://www.google.com/speech-api/v2/recognize",
    }
    logged = _logged_fields(logger)
    assert request_error_marker not in logged
    assert "SHARED_KEY_SENTINEL" not in logged
    assert "https://example.invalid" not in logged
    assert "RequestError" in logged


def test_integrated_recognition_does_not_log_text_dictionary_or_model_reason() -> (
    None
):
    logger = MagicMock()
    google_text = "GOOGLE_TRANSCRIPT_SENTINEL"
    groq_text = "GROQ_TRANSCRIPT_SENTINEL"
    selected_text = "SELECTED_TRANSCRIPT_SENTINEL"
    dictionary_word = "CUSTOM_DICTIONARY_SENTINEL"
    reason = "MODEL_REASON_SENTINEL"
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=f'{{"estimated_text":"{selected_text}","reason":"{reason}"}}'
                    )
                )
            ]
        )
    )
    recognizer = object.__new__(IntegratedSpeechRecognizer)
    recognizer._logger = cast(BoundLogger, logger)
    recognizer.custom_dictionary = [dictionary_word]
    recognizer.integrator_model = "model-id"
    recognizer.language = "ja-JP"
    recognizer.primary_language = "ja"
    recognizer._groq = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    recognizer.recognize_google = AsyncMock(return_value=google_text)
    recognizer.recognize_groq = AsyncMock(return_value=groq_text)
    audio = _audio()

    result = asyncio.run(recognizer.recognize(audio, has_voice_activity=True))

    assert result == selected_text
    assert google_text in repr(create.call_args.kwargs["messages"])
    assert groq_text in repr(create.call_args.kwargs["messages"])
    assert dictionary_word in repr(create.call_args.kwargs["messages"])
    logged = _logged_fields(logger)
    for marker in (
        google_text,
        groq_text,
        selected_text,
        dictionary_word,
        reason,
    ):
        assert marker not in logged
    assert f"result_length={len(selected_text)}" in logged


def test_groq_transcription_does_not_log_transcript_or_segment_text() -> None:
    logger = MagicMock()
    transcript = "GROQ_TRANSCRIPT_ONLY_SENTINEL"
    segment_text = "GROQ_SEGMENT_ONLY_SENTINEL"
    create = AsyncMock(
        return_value=SimpleNamespace(
            text=transcript,
            segments=[{"text": segment_text, "no_speech_prob": 0.1}],
        )
    )
    recognizer = object.__new__(IntegratedSpeechRecognizer)
    recognizer._logger = cast(BoundLogger, logger)
    recognizer._groq = SimpleNamespace(
        audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create))
    )
    recognizer.groq_model = "whisper-model"
    recognizer._no_speech_prob_threshold = 0.9
    audio = _audio()

    result = asyncio.run(recognizer.recognize_groq(audio, "ja"))

    assert result == transcript
    logged = _logged_fields(logger)
    assert transcript not in logged
    assert segment_text not in logged
    assert f"result_length={len(transcript)}" in logged


def test_invalid_integrator_response_is_not_in_exception() -> None:
    response_body = "MODEL_RESPONSE_BODY_SENTINEL"
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=response_body))
            ]
        )
    )
    recognizer = object.__new__(IntegratedSpeechRecognizer)
    recognizer._groq = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    recognizer.integrator_model = "model-id"
    recognizer.custom_dictionary = []

    with pytest.raises(RuntimeError) as raised:
        asyncio.run(recognizer._estimate_speech("input transcript"))

    assert str(raised.value) == "音声認識の統合結果を読み取れませんでした"
    assert response_body not in str(raised.value)
    assert raised.value.__suppress_context__ is True


def test_google_tts_does_not_log_text_or_key_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    text = "TTS_TEXT_SENTINEL"
    key = "TTS_KEY_SENTINEL"
    settings = VideoEditSettings(
        speech=SubtitleSpeechSettings(
            enabled=True, google_api_key=SecretStr(key)
        )
    )
    adapter = GoogleTextToSpeech(settings, cast(BoundLogger, logger))
    request = SpeechSynthesisRequest(
        text=text,
        language_code="ja-JP",
        voice_name="voice",
        speaking_rate=1.0,
        pitch=0.0,
        audio_encoding="LINEAR16",
        sample_rate_hz=24000,
    )
    response = MagicMock()
    response.json.return_value = {
        "audioContent": base64.b64encode(b"audio").decode()
    }
    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.audio.google_text_to_speech.httpx.post",
        lambda *args, **kwargs: response,
    )

    adapter.synthesize(request)

    logged = _logged_fields(logger)
    assert text not in logged
    assert key not in logged
    assert f"text_length={len(text)}" in logged


def test_google_tts_provider_failure_is_sanitized_and_unlinked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    text = "TTS_ERROR_TEXT_SENTINEL"
    key = "TTS_ERROR_KEY_SENTINEL"
    adapter = GoogleTextToSpeech(
        VideoEditSettings(
            speech=SubtitleSpeechSettings(
                enabled=True, google_api_key=SecretStr(key)
            )
        ),
        cast(BoundLogger, logger),
    )
    request = SpeechSynthesisRequest(
        text=text,
        language_code="ja-JP",
        voice_name="voice",
        speaking_rate=1.0,
        pitch=0.0,
        audio_encoding="LINEAR16",
        sample_rate_hz=24000,
    )

    def fail_request(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError(
            f"https://texttospeech.googleapis.com/?key={key} {text}"
        )

    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.audio.google_text_to_speech.httpx.post",
        fail_request,
    )

    with pytest.raises(RuntimeError) as raised:
        adapter.synthesize(request)

    assert (
        str(raised.value) == "Google Text-to-Speech の呼び出しに失敗しました"
    )
    assert raised.value.__suppress_context__ is True
    logged = _logged_fields(logger)
    assert text not in logged
    assert key not in logged
    assert "texttospeech.googleapis.com" not in logged
    assert "ConnectError" in logged
