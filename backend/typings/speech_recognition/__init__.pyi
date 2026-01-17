"""speech_recognition ライブラリの型スタブ"""

from typing import Any

class AudioData:
    """音声データ"""

    frame_data: bytes
    sample_rate: int
    sample_width: int

    def get_raw_data(
        self, convert_rate: int | None = None, convert_width: int | None = None
    ) -> bytes: ...

class Microphone:
    """マイクロフォン"""
    def __init__(
        self,
        device_index: int | None = None,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
    ) -> None: ...
    def __enter__(self) -> Microphone: ...
    def __exit__(self, *args: Any) -> None: ...
    @staticmethod
    def list_microphone_names() -> list[str]: ...

class AudioFile:
    """音声ファイル"""
    def __init__(self, filename_or_fileobject: str) -> None: ...
    def __enter__(self) -> AudioFile: ...
    def __exit__(self, *args: Any) -> None: ...

class Recognizer:
    """音声認識エンジン"""
    def __init__(self) -> None: ...
    def recognize_google(
        self,
        audio_data: AudioData,
        key: str | None = None,
        language: str = "en-US",
        show_all: bool = False,
    ) -> str: ...
    def recognize_groq(
        self,
        audio_data: AudioData,
        model: str = "whisper-large-v3",
        language: str | None = None,
    ) -> str: ...
    def listen(
        self,
        source: Microphone,
        timeout: float | None = None,
        phrase_time_limit: float | None = None,
    ) -> AudioData: ...
    def record(self, source: AudioFile) -> AudioData: ...
    def adjust_for_ambient_noise(
        self,
        source: Microphone,
        duration: float = 1,
    ) -> None: ...

class UnknownValueError(Exception):
    """音声認識できなかった場合のエラー"""

    ...

class RequestError(Exception):
    """音声認識リクエストエラー"""

    ...

class WaitTimeoutError(Exception):
    """タイムアウトエラー"""

    ...
