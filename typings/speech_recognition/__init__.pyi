from __future__ import annotations

from types import TracebackType

class AudioData:
    frame_data: bytes
    sample_width: int
    sample_rate: int
    def get_raw_data(
        self, convert_rate: int | None = ..., convert_width: int | None = ...
    ) -> bytes: ...

class UnknownValueError(Exception): ...
class RequestError(Exception): ...
class WaitTimeoutError(Exception): ...

class Microphone:
    @staticmethod
    def list_microphone_names() -> list[str]: ...
    def __init__(
        self,
        device_index: int | None = ...,
        sample_rate: int | None = ...,
        chunk_size: int | None = ...,
    ) -> None: ...
    def __enter__(self) -> Microphone: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None: ...

class Recognizer:
    energy_threshold: float

    def listen(
        self,
        source: Microphone,
        *,
        timeout: float | None = ...,
        phrase_time_limit: float | None = ...,
    ) -> AudioData: ...
    def adjust_for_ambient_noise(
        self, source: Microphone, duration: float = ...
    ) -> None: ...
    def recognize_google(
        self, audio: AudioData, *, language: str = ...
    ) -> str: ...
    def recognize_groq(
        self,
        audio: AudioData,
        *,
        model: str = ...,
        language: str | None = ...,
    ) -> str: ...
