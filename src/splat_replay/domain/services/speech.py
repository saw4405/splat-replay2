"""音声認識サービス。"""

from __future__ import annotations

from pathlib import Path


class SpeechTranscriber:
    """Groq API を用いた文字起こし処理を提供する。"""

    def start_capture(self) -> None:
        """音声キャプチャを開始する。"""
        raise NotImplementedError

    def stop_capture(self) -> Path:
        """録音ファイルのパスを返しつつキャプチャを停止する。"""
        raise NotImplementedError

    def transcribe(self, audio: Path) -> str:
        """音声ファイルをテキストに変換する。"""
        raise NotImplementedError
