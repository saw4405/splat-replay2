"""Groq API クライアント。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.shared.logger import get_logger

logger = get_logger()


class GroqClient:
    """音声を文字起こしする。"""

    def transcribe(self, audio: Path) -> str:
        """音声ファイルをテキスト化する。"""
        logger.info("音声をテキスト化", audio=str(audio))
        raise NotImplementedError
