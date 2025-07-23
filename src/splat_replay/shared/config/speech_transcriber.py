from typing import List

from pydantic import BaseModel


class SpeechTranscriberSettings(BaseModel):
    """音声認識処理の設定。"""

    mic_device_name: str = "マイク (USB Audio Device)"
    groq_api_key: str = ""
    language: str = "ja-JP"
    phrase_time_limit: float = 3.0
    custom_dictionary: List[str] = ["ナイス", "キル", "デス"]

    class Config:
        pass
