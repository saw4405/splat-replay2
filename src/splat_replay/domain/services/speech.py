"""音声認識サービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.shared.logger import get_logger

logger = get_logger()


class SpeechTranscriber:
    """Groq API を用いた文字起こし処理を提供する。"""

    def start_capture(self) -> None:
        """音声キャプチャを開始する。"""
        logger.info("音声キャプチャ開始")
        # raise NotImplementedError

    def stop_capture(self) -> Path:
        """録音ファイルのパスを返しつつキャプチャを停止する。"""
        logger.info("音声キャプチャ停止")
        # raise NotImplementedError
        return Path("dummy_audio.wav")

    def transcribe(self, audio: Path) -> str:
        """音声ファイルをテキストに変換する。"""
        logger.info("音声文字起こし", audio=str(audio))
        # raise NotImplementedError
        return "ダミーの文字起こし結果です。"
