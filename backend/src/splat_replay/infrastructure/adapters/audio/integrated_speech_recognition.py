import asyncio
import math
import os
from typing import Optional

import speech_recognition as sr
import webrtcvad
from groq import AsyncGroq
from pydantic import BaseModel
from structlog.stdlib import BoundLogger

from splat_replay.domain.config import SpeechTranscriberSettings


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

        self.groq_model = settings.groq_model
        self.integrator_model = settings.integrator_model
        self.language = settings.language
        self.primary_language = settings.language.split("-")[0]
        self.custom_dictionary = settings.custom_dictionary
        self._logger = logger
        self._recognizer: sr.Recognizer = sr.Recognizer()
        self._groq = AsyncGroq()
        self._vad = webrtcvad.Vad(settings.vad_aggressiveness)
        self._vad_min_speech_frames = settings.vad_min_speech_frames
        self._vad_min_speech_ratio = settings.vad_min_speech_ratio

    def _has_voice_activity(self, audio: sr.AudioData) -> bool:
        """VAD を用いて音声活動を判定する。"""

        try:
            pcm16 = audio.get_raw_data(convert_rate=16000, convert_width=2)
        except Exception as exc:
            self._logger.error(
                f"音声データの変換に失敗したためVADを実行できません: {exc}"
            )
            return True

        frame_duration_ms = 30
        bytes_per_frame = int(16000 * 2 * frame_duration_ms / 1000)
        if len(pcm16) < bytes_per_frame:
            self._logger.debug(
                "VAD判定に必要なフレーム長を満たしていないため無音と判定しました"
            )
            return False

        speech_frames = 0
        total_frames = 0
        for start in range(
            0, len(pcm16) - bytes_per_frame + 1, bytes_per_frame
        ):
            frame = pcm16[start : start + bytes_per_frame]
            total_frames += 1
            if self._vad.is_speech(frame, 16000):
                speech_frames += 1

        if total_frames == 0:
            self._logger.debug(
                "VAD判定対象のフレームが存在しないため無音と判定しました"
            )
            return False

        required_frames = max(
            self._vad_min_speech_frames,
            math.ceil(total_frames * self._vad_min_speech_ratio),
        )
        self._logger.debug(
            "VAD判定結果",
            total_frames=total_frames,
            speech_frames=speech_frames,
            required_frames=required_frames,
        )
        if speech_frames >= required_frames:
            return True

        self._logger.debug(
            "VADが音声活動を検出しなかったため無音と判定しました"
        )
        return False

    def has_voice_activity(self, audio: sr.AudioData) -> bool:
        """VAD を用いた音声活動の判定結果を返す。"""
        return self._has_voice_activity(audio)

    async def recognize(
        self, audio: sr.AudioData, has_voice_activity: Optional[bool] = None
    ) -> Optional[str]:
        if has_voice_activity is None:
            has_voice_activity = self._has_voice_activity(audio)
        if not has_voice_activity:
            return None

        google, groq = await asyncio.gather(
            self.recognize_google(audio, self.language),
            self.recognize_groq(audio, self.primary_language),
        )
        if google is None:
            self._logger.info(
                "Google音声認識の結果が空のためスキップします (音声なしと判断)",
                groq=groq,
            )
            return None
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
                self._logger.debug(f"google: {result}")
                return result
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                self._logger.error("Google音声認識エラー", error=str(e))
                return None

        return await asyncio.to_thread(_recognize_google)

    async def recognize_groq(
        self, audio: sr.AudioData, language: str
    ) -> Optional[str]:
        def _recognize_groq() -> Optional[str]:
            try:
                result = self._recognizer.recognize_groq(
                    audio,
                    model=self.groq_model,
                    language=language,
                )
                self._logger.debug(f"groq: {result}")
                return result
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                self._logger.error("Groq音声認識エラー", error=str(e))
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

        # Groq SDK: messages/response_formatの型定義が不完全なためtype:ignoreで対処
        response_fmt: object = {"type": "json_object"}
        chat_completion = await self._groq.chat.completions.create(  # type: ignore[arg-type]
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
            model=self.integrator_model,
            temperature=0,
            stream=False,
            response_format=response_fmt,  # type: ignore[arg-type]
        )
        res = chat_completion.choices[0].message.content
        if res is None:
            raise RuntimeError("Failed to estimate speech")

        try:
            return RecognitionResult.parse_raw(res)
        except Exception as e:
            raise RuntimeError(f"Failed to validate JSON: {e}")
