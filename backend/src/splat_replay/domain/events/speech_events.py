"""Speech recognition domain events.

Events related to speech recognition and transcription.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from splat_replay.domain.events.base import DomainEvent


@dataclass(frozen=True)
class SpeechRecognizerListening(DomainEvent):
    """Speech recognizer is actively listening for audio input."""

    EVENT_TYPE: ClassVar[str] = "domain.speech.listening"


@dataclass(frozen=True)
class SpeechRecognized(DomainEvent):
    """Speech has been recognized and transcribed."""

    EVENT_TYPE: ClassVar[str] = "domain.speech.recognized"

    text: str = ""
    start_seconds: float = 0.0
    end_seconds: float = 0.0


__all__ = [
    "SpeechRecognizerListening",
    "SpeechRecognized",
]
