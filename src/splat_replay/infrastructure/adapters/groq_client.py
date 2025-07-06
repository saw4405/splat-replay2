from __future__ import annotations


class GroqClient:
    """音声認識用のダミークライアント."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    def transcribe(self, audio_path: str) -> str:
        return ""
