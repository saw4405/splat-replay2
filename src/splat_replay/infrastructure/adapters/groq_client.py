"""Groq API クライアント。"""

from __future__ import annotations

from pathlib import Path


class GroqClient:
    """音声を文字起こしする。"""

    def transcribe(self, audio: Path) -> str:
        """音声ファイルをテキスト化する。"""
        raise NotImplementedError
