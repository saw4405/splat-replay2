"""Google Text-to-Speech API アダプタ."""

from __future__ import annotations

import base64

import httpx
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    TextToSpeechPort,
)
from splat_replay.shared.config import VideoEditSettings


class GoogleTextToSpeech(TextToSpeechPort):
    """Google Cloud Text-to-Speech を利用した読み上げアダプタ."""

    _ENDPOINT = "https://texttospeech.googleapis.com/v1beta1/text:synthesize"

    def __init__(
        self, settings: VideoEditSettings, logger: BoundLogger
    ) -> None:
        speech_settings = settings.speech
        if not speech_settings.enabled:
            raise ValueError("字幕読み上げが無効化されています")
        if speech_settings.provider != "google":
            raise ValueError("Google 読み上げが選択されていません")
        api_key = speech_settings.google_api_key.get_secret_value().strip()
        if not api_key:
            raise ValueError("Google Cloud API キーが設定されていません")
        self._api_key = api_key
        self._model = speech_settings.model.strip() or None
        self._logger = logger
        self._timeout = 30.0

    def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> SpeechSynthesisResult:
        voice_payload: dict[str, object] = {
            "languageCode": request.language_code,
            "name": request.voice_name,
        }
        if self._model:
            voice_payload["model"] = self._model
        payload: dict[str, object] = {
            "input": {"text": request.text},
            "voice": voice_payload,
            "audioConfig": {
                "audioEncoding": request.audio_encoding,
                "speakingRate": request.speaking_rate,
                "pitch": request.pitch,
                "sampleRateHertz": request.sample_rate_hz,
            },
        }

        self._logger.info(
            "Google TTS へリクエストを送信します",
            payload={"text": request.text},
        )
        try:
            response = httpx.post(
                f"{self._ENDPOINT}?key={self._api_key}",
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._logger.error(
                "Google TTS リクエストに失敗しました", error=str(exc)
            )
            raise RuntimeError(
                "Google Text-to-Speech の呼び出しに失敗しました"
            ) from exc

        data = response.json()
        if not isinstance(data, dict):
            self._logger.error("Google TTS 応答が不正です")
            raise RuntimeError("Google Text-to-Speech の応答形式が不正です")

        audio_content = data.get("audioContent")
        if not isinstance(audio_content, str) or not audio_content:
            self._logger.error("Google TTS 応答に音声データが含まれていません")
            raise RuntimeError(
                "Google Text-to-Speech の応答に音声データがありません"
            )

        try:
            audio_bytes = base64.b64decode(audio_content)
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Google TTS 音声デコード失敗", error=str(exc))
            raise RuntimeError(
                "Google Text-to-Speech の音声データをデコードできませんでした"
            ) from exc

        return SpeechSynthesisResult(
            audio=audio_bytes, sample_rate_hz=request.sample_rate_hz
        )
