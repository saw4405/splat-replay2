import os

import speech_recognition as sr
from groq import Groq
from pydantic import BaseModel

from splat_replay.application.interfaces import SpeechRecognizerPort
from splat_replay.shared.config import SpeechTranscriberSettings
from splat_replay.shared.logger import get_logger


class RecognitionResult(BaseModel):
    estimated_text: str
    reason: str


class IntegratedSpeechRecognizer(SpeechRecognizerPort):
    def __init__(self, settings: SpeechTranscriberSettings):
        os.environ["GROQ_API_KEY"] = settings.groq_api_key
        self.language = settings.language
        self.primary_language = settings.language.split("-")[0]
        self.custom_dictionary = settings.custom_dictionary
        self._logger = get_logger()
        self._recognizer = sr.Recognizer()
        self._groq = Groq()

    def recognize(self, audio: sr.AudioData) -> str | None:
        try:
            google: str = self._recognizer.recognize_google(  # type: ignore
                audio, language=self.language
            )
            self._logger.info(f"google: {google}")
            groq: str = self._recognizer.recognize_groq(  # type: ignore
                audio, model="whisper-large-v3", language=self.primary_language
            )
            self._logger.info(f"groq: {groq}")
            result = self._estimate_speech(f"google: {google}\ngroq: {groq}")
            self._logger.info(
                f"推定: {result.estimated_text} 理由: {result.reason}"
            )
            return result.estimated_text

        except sr.UnknownValueError as e:
            return None

        except sr.RequestError as e:
            self._logger.error(
                f"音声認識エンジンへのリクエストが失敗しました: {e}"
            )
            return None

        except Exception as e:
            self._logger.error(f"音声認識エラー: {e}")
            return None

    def _estimate_speech(self, results: str) -> RecognitionResult:
        system_message = (
            "あなたは複数の音声認識エンジンから得られた認識結果をもとに、オリジナルの発言を推定する役割を担います。"
            "入力された認識結果に対して、不要な置き換えや意訳は一切行わず、可能な限り入力内容に忠実に出力してください。"
            "例えば、認識結果中の単語や表現がそのまま引用されるべき場合、意図的な変更は行わないこと。"
            "出力はあらかじめ定義されたJSONスキーマに準拠し、入力された内容の本質を反映するものにしてください。"
            f"単語集: {'、'.join(self.custom_dictionary)}\n"
            f" The JSON object must use the schema: {RecognitionResult.schema_json(indent=2)}"
        )

        chat_completion = self._groq.chat.completions.create(
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
            model="llama-3.3-70b-versatile",
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
