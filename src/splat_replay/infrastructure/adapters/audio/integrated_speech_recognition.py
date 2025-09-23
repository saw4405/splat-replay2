import asyncio
import os
from typing import Optional

import speech_recognition as sr
from groq import AsyncGroq
from pydantic import BaseModel
from structlog.stdlib import BoundLogger

from splat_replay.shared.config import SpeechTranscriberSettings


class RecognitionResult(BaseModel):
    estimated_text: str
    reason: str


class IntegratedSpeechRecognizer:
    def __init__(
        self,
        settings: SpeechTranscriberSettings,
        logger: BoundLogger,
    ):
        os.environ["GROQ_API_KEY"] = settings.groq_api_key.get_secret_value()
        self.model = settings.model
        self.language = settings.language
        self.primary_language = settings.language.split("-")[0]
        self.custom_dictionary = settings.custom_dictionary
        self._logger = logger
        self._recognizer = sr.Recognizer()
        self._groq = AsyncGroq()

    async def recognize(self, audio: sr.AudioData) -> Optional[str]:
        google, groq = await asyncio.gather(
            self.recognize_google(audio, self.language),
            self.recognize_groq(audio, self.primary_language),
        )
        result = await self._estimate_speech(f"google: {google}\ngroq: {groq}")
        self._logger.info(
            f"推定: {result.estimated_text} 理由: {result.reason}"
        )
        return result.estimated_text

    async def recognize_google(
        self, audio: sr.AudioData, language: str
    ) -> Optional[str]:
        def _recognize_google() -> Optional[str]:
            try:
                result = self._recognizer.recognize_google(
                    audio, language=language
                )
                self._logger.info(f"google: {result}")
                return result
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                self._logger.error(f"Google音声認識エラー: {e}")
                return None

        return await asyncio.to_thread(_recognize_google)

    async def recognize_groq(
        self, audio: sr.AudioData, language: str
    ) -> Optional[str]:
        def _recognize_groq() -> Optional[str]:
            try:
                result = self._recognizer.recognize_groq(
                    audio, model="whisper-large-v3", language=language
                )
                self._logger.info(f"groq: {result}")
                return result
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                self._logger.error(f"Groq音声認識エラー: {e}")
                return None

        return await asyncio.to_thread(_recognize_groq)

    async def _estimate_speech(self, results: str) -> RecognitionResult:
        system_message = (
            "あなたは複数の音声認識エンジンから得られた認識結果をもとに、オリジナルの発言を推定する役割を担います。"
            "入力された認識結果に対して、不要な置き換えや意訳は一切行わず、可能な限り入力内容に忠実に出力してください。"
            "例えば、認識結果中の単語や表現がそのまま引用されるべき場合、意図的な変更は行わないこと。"
            "出力はあらかじめ定義されたJSONスキーマに準拠し、入力された内容の本質を反映するものにしてください。"
            f"単語集: {'、'.join(self.custom_dictionary)}\n"
            f" The JSON object must use the schema: {RecognitionResult.schema_json(indent=2)}"
        )

        chat_completion = await self._groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_message,
                },
                {
                    "role": "user",
                    "content": results,
                },
            ],
            model=self.model,
            temperature=0,
            stream=False,
            response_format={"type": "json_object"},
        )
        res = chat_completion.choices[0].message.content
        if res is None:
            raise RuntimeError("Failed to estimate speech")

        try:
            return RecognitionResult.parse_raw(res)
        except Exception as e:
            raise RuntimeError(f"Failed to validate JSON: {e}")
