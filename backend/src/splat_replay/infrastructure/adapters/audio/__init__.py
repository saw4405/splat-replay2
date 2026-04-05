"""音声アダプター公開面の遅延 import 設定。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "IntegratedSpeechRecognizer",
    "MicrophoneEnumerator",
    "SpeechTranscriber",
    "GoogleTextToSpeech",
]

_LAZY_EXPORTS = {
    "IntegratedSpeechRecognizer": (
        ".integrated_speech_recognition",
        "IntegratedSpeechRecognizer",
    ),
    "MicrophoneEnumerator": (
        ".microphone_enumerator",
        "MicrophoneEnumerator",
    ),
    "SpeechTranscriber": (
        ".speech_transcriber",
        "SpeechTranscriber",
    ),
    "GoogleTextToSpeech": (
        ".google_text_to_speech",
        "GoogleTextToSpeech",
    ),
}


def __getattr__(name: str) -> Any:
    """必要になったアダプターだけを import する。"""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _LAZY_EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
