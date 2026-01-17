from typing import List

from pydantic import BaseModel, Field, SecretStr


class SpeechTranscriberSettings(BaseModel):
    """文字起こし"""

    enabled: bool = Field(
        default=True,
        title="文字起こしを有効にする",
        description="文字起こし機能を使用するかどうかを切り替えます",
        recommended=True,
        user_editable=True,
    )
    mic_device_name: str = Field(
        default="マイク (USB Audio Device)",
        title="マイクデバイス名",
        description="OSが認識しているマイクの名称",
        recommended=True,
        user_editable=True,
    )
    groq_api_key: SecretStr = Field(
        default=SecretStr(""),
        title="Groq API キー",
        description="Groq API の認証に使用するキー",
        recommended=True,
        user_editable=True,
    )
    groq_model: str = Field(
        default="whisper-large-v3",
        title="Groq音声認識モデル",
        description="使用するGroq音声認識モデル",
        recommended=False,
    )
    integrator_model: str = Field(
        default="openai/gpt-oss-120b",
        title="音声認識統合モデル",
        description="複数の音声認識結果を統合するためのモデル",
        recommended=False,
    )
    language: str = Field(
        default="ja-JP",
        title="言語",
        description="音声認識に使用する言語",
        recommended=False,
        user_editable=False,
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
        description="音声認識の精度を向上させるための単語リスト",
        recommended=True,
        user_editable=True,
    )
    vad_aggressiveness: int = Field(
        default=2,
        title="VAD感度",
        description=(
            "0〜3の値でVADの厳しさを指定します。値が大きいほど無音を厳しく判定します"
        ),
        ge=0,
        le=3,
        recommended=False,
    )
    vad_min_speech_frames: int = Field(
        default=3,
        title="VAD最小検出フレーム数",
        description="VADで音声ありと判定するために必要な最小フレーム数",
        ge=1,
        recommended=False,
    )
    vad_min_speech_ratio: float = Field(
        default=0.1,
        title="VAD最小検出比率",
        description="VADで音声ありと判定するために必要なフレーム比率 (0.0〜1.0)",
        ge=0.0,
        le=1.0,
        recommended=False,
    )

    class Config:
        pass
