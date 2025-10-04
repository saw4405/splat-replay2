from typing import Literal

from pydantic import BaseModel, Field, SecretStr


SpeechAudioEncodingLiteral = Literal["LINEAR16", "MP3", "OGG_OPUS"]


class SubtitleSpeechSettings(BaseModel):
    """字幕読み上げの設定。"""

    enabled: bool = Field(
        default=False,
        title="字幕読み上げを有効化",
        description="字幕から読み上げ音声を生成して動画に追加します",
        recommended=False,
    )
    provider: Literal["google"] = Field(
        default="google",
        title="読み上げプロバイダ",
        description="使用する読み上げサービス",
        recommended=False,
    )
    google_api_key: SecretStr = Field(
        default=SecretStr(""),
        title="Google Cloud API キー",
        description="Google Text-to-Speech API を呼び出すためのキー",
        recommended=True,
    )
    model: str = Field(
        default="",
        title="モデル",
        description="利用する読み上げモデル。空の場合はデフォルトモデルを使用します",
        recommended=False,
    )
    voice_name: str = Field(
        default="ja-JP-Chirp3-HD-Despina",
        title="ボイス名",
        description="利用するボイスの識別子",
        recommended=False,
    )
    language_code: str = Field(
        default="ja-JP",
        title="言語コード",
        description="読み上げに使用する言語コード",
        recommended=False,
    )
    speaking_rate: float = Field(
        default=1.0,
        title="読み上げ速度",
        description="読み上げ速度倍率",
        recommended=False,
    )
    pitch: float = Field(
        default=0.0,
        title="読み上げピッチ",
        description="読み上げ音声のピッチ",
        recommended=False,
    )
    audio_encoding: SpeechAudioEncodingLiteral = Field(
        default="LINEAR16",
        title="音声エンコーディング",
        description="生成される音声データのエンコーディング形式",
        recommended=False,
    )
    sample_rate_hz: int = Field(
        default=24000,
        title="サンプルレート",
        description="生成される音声データのサンプルレート (Hz)",
        recommended=False,
    )
    track_title: str = Field(
        default="字幕読み上げ",
        title="トラックタイトル",
        description="動画に追加する音声トラックのタイトル",
        recommended=False,
    )


class VideoEditSettings(BaseModel):
    """動画編集"""

    volume_multiplier: float = Field(
        default=1.0,
        title="音量倍率",
        description="動画の音量を調整する倍率",
        recommended=False,
    )
    title_template: str = Field(
        default="{BATTLE}({RATE}) {RULE} {WIN}勝{LOSE}敗 {DAY:'%y.%m.%d} {SCHEDULE:%H}時～",
        title="タイトルテンプレート",
        description="動画のタイトルに使用するテンプレート",
        recommended=False,
    )
    description_template: str = Field(
        default="{CHAPTERS}",
        title="説明テンプレート",
        description="動画の説明に使用するテンプレート",
        recommended=False,
    )
    chapter_template: str = Field(
        default="{RESULT:<5} {KILL:>3}k {DEATH:>3}d {SPECIAL:>3}s  {STAGE}",
        title="チャプターテンプレート",
        description="動画の説明欄に入るチャプターに使用するテンプレート",
        recommended=False,
    )
    speech: SubtitleSpeechSettings = Field(
        default_factory=SubtitleSpeechSettings,
        title="字幕読み上げ設定",
        description="字幕読み上げ音声の生成と結合に関する設定",
        recommended=False,
    )

    class Config:
        pass
