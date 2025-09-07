from typing import List

from pydantic import BaseModel, Field, SecretStr


class SpeechTranscriberSettings(BaseModel):
    """文字起こし"""

    mic_device_name: str = Field(
        default="マイク (USB Audio Device)",
        title="マイクデバイス名",
        description="OSが認識しているマイクの名称\n文字起こししない場合は空文字列",
        recommended=True,
    )
    groq_api_key: SecretStr = Field(
        default=SecretStr(""),
        title="Grok API キー",
        description="Grok API の認証に使用するキー",
        recommended=True,
    )
    model: str = Field(
        default="",
        title="モデル",
        description="使用する音声認識モデル",
        recommended=False,
    )
    language: str = Field(
        default="ja-JP",
        title="言語",
        description="音声認識に使用する言語",
        recommended=False,
    )
    phrase_time_limit: float = Field(
        default=3.0,
        title="フレーズの最大長",
        description="音声認識で処理するフレーズの最大長",
        recommended=False,
    )
    custom_dictionary: List[str] = Field(
        default=["ナイス", "キル", "デス"],
        title="カスタム辞書",
        description="音声認識に使用するカスタム辞書",
        recommended=True,
    )

    class Config:
        pass
