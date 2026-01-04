"""各種アダプタ実装を公開するモジュール。"""

__all__ = [
    "IntegratedSpeechRecognizer",
    "SpeechTranscriber",
    "GoogleTextToSpeech",
]

from .google_text_to_speech import GoogleTextToSpeech
from .integrated_speech_recognition import IntegratedSpeechRecognizer
from .speech_transcriber import SpeechTranscriber
