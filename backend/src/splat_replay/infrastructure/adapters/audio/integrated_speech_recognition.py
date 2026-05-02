import asyncio
import io
import math
import os
from typing import Any, Optional

import speech_recognition as sr
import webrtcvad
from groq import AsyncGroq
from pydantic import BaseModel
from splat_replay.domain.config import SpeechTranscriberSettings
from structlog.stdlib import BoundLogger


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
        self._no_speech_prob_threshold = settings.no_speech_prob_threshold

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

        self._logger.info(
            "VADが音声活動を検出しなかったため無音と判定しました",
            speech_frames=speech_frames,
            required_frames=required_frames,
            total_frames=total_frames,
            vad_min_speech_frames=self._vad_min_speech_frames,
            vad_min_speech_ratio=self._vad_min_speech_ratio,
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
            self._logger.debug(
                "Google音声認識の結果が空のためスキップします (音声なしと判断)",
                groq=groq,
            )
            return None
        result = await self._estimate_speech(f"google: {google}\ngroq: {groq}")
        self._logger.info(f"音声認識結果: {result.estimated_text!r}")
        self._logger.debug(f"推定理由: {result.reason}")
        return result.estimated_text or None

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
        wav_bytes = await asyncio.to_thread(audio.get_wav_data)
        wav_file: Any = io.BytesIO(wav_bytes)
        wav_file.name = "audio.wav"

        try:
            transcription: Any = await self._groq.audio.transcriptions.create(
                file=wav_file,
                model=self.groq_model,
                language=language,
                response_format="verbose_json",
            )
        except Exception as e:
            self._logger.error("Groq音声認識エラー", error=str(e))
            return None

        # no_speech_prob で無音判定（segments は dict のリスト）
        segments: list[dict[str, Any]] = (
            getattr(transcription, "segments", None) or []
        )
        if segments:
            avg_no_speech_prob: float = sum(
                s.get("no_speech_prob", 0.0) for s in segments
            ) / len(segments)
            self._logger.debug(
                "Groq no_speech_prob",
                avg=avg_no_speech_prob,
                threshold=self._no_speech_prob_threshold,
                segments=[
                    (s.get("text", ""), s.get("no_speech_prob"))
                    for s in segments
                ],
            )
            if avg_no_speech_prob >= self._no_speech_prob_threshold:
                self._logger.info(
                    "Groq: no_speech_prob が閾値以上のため無音と判定",
                    avg_no_speech_prob=avg_no_speech_prob,
                    no_speech_prob_threshold=self._no_speech_prob_threshold,
                )
                return None
        else:
            self._logger.debug(
                "Groq: segments なし（verbose_json 未対応の可能性）"
            )

        text = (transcription.text or "").strip()
        self._logger.debug(f"groq: {text!r}")
        return text or None

    async def _estimate_speech(self, results: str) -> RecognitionResult:
        system_message = (
            "あなたは、同一の音声を2つの音声認識エンジン（Google・Groq Whisper）で書き起こした結果を受け取り、"
            "実際に発話されたテキストを推定する役割を担います。\n\n"
            "## 前提\n"
            "- 入力は同じ音声に対する2つの認識結果です。\n"
            "- 結果が大きく異なる場合、どちらかが誤りです。両方を足したり混ぜたりしないでください。\n"
            "- Groq (Whisper) はノイズや無音時に幻覚テキストを生成することがあります（例: 学習データ由来の定型句）。\n\n"
            "## 判断方針\n"
            "1. 両者が一致・類似している → その内容を採用する。\n"
            "2. 片方だけに意味のあるテキストがある → もう一方を優先するが、Whisperの幻覚の可能性も考慮する。\n"
            "3. 両者が全く異なる → より自然で文脈的に妥当な方を一つ選ぶ。決して両方を連結しないこと。\n"
            "4. どちらも信頼できないと判断した場合 → estimated_text を空文字列にする。\n\n"
            "## 出力形式\n"
            f"単語集（優先的に認識すべき語）: {'、'.join(self.custom_dictionary)}\n"
            "必ず以下のキーを持つJSONオブジェクトのみを返してください（余分なキーは含めないこと）:\n"
            '{"estimated_text": "<推定テキスト>", "reason": "<判断理由>"}\n\n'
            f"スキーマ参考: {RecognitionResult.schema_json(indent=2)}"
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
            raise RuntimeError(
                f"Failed to validate JSON: {e}\nraw response: {res}"
            )
