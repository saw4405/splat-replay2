"""Audio processing ports (speech, TTS, transcription)."""

from __future__ import annotations

from typing import Protocol

from splat_replay.application.interfaces.data import (
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
)


class TextToSpeechPort(Protocol):
    """テキスト読み上げ処理を提供するポート。"""

    def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> SpeechSynthesisResult:
        """Synthesize speech from text."""
        ...


class SpeechTranscriberPort(Protocol):
    """音声文字起こし処理を提供するポート。"""

    def start(self) -> None:
        """Start transcription."""
        ...

    def stop(self) -> str:
        """Stop transcription and return transcript."""
        ...

    def pause(self) -> None:
        """Pause transcription."""
        ...

    def resume(self) -> None:
        """Resume transcription."""
        ...
