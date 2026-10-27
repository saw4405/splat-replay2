from typing import Literal
from string import Formatter
import re

from pydantic import BaseModel, Field, SecretStr, validator

THUMBNAIL_VARIABLES = {
    "WIN": 4,
    "LOSE": 3,
    "RATE": "XP: 2000.0",
    "RATE_LABEL": "XP: ",
    "RATE_VALUE": "2000.0",
    "RATE_MIN": "2000.0",
    "RATE_MAX": "2100.0",
    "BATTLE": "Xマッチ",
    "RULE": "ガチエリア",
    "STAGES": "サンプルステージ",
}


class ThumbnailElement(BaseModel):
    """描画順に並べるサムネイル要素。座標は1920×1080基準。"""

    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    source: Literal[
        "win_lose",
        "rate",
        "match",
        "rule_label",
        "rule_icon",
        "stages",
        "highlights",
        "overlay",
        "text",
        "shape",
        "image",
    ]
    visible: bool = True
    x: int = Field(default=0, ge=-7680, le=7680)
    y: int = Field(default=0, ge=-4320, le=4320)
    width: int = Field(default=0, ge=0, le=3840)
    height: int = Field(default=0, ge=0, le=2160)
    template: str = Field(default="", max_length=1000)
    asset: str = ""
    font: str = "Paintball_Beta.otf"
    font_size: int = Field(default=70, ge=8, le=300)
    color: str = "#ffffff"
    auto_color: bool = False
    outline_color: str = "#000000"
    outline_width: int = Field(default=0, ge=0, le=20)
    center: bool = False
    shape: Literal["rectangle", "rounded_rectangle", "ellipse"] = "rectangle"
    radius: int = Field(default=40, ge=0, le=1000)
    opacity: float = Field(default=1, ge=0, le=1)

    @validator("color", "outline_color")
    def valid_color(cls, value: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("色は #RRGGBB 形式で指定してください")
        return value

    @validator("asset", "font")
    def safe_asset(cls, value: str) -> str:
        if value and (
            value.startswith("/")
            or "\\" in value
            or any(p in ("", ".", "..") for p in value.split("/"))
            or ":" in value
        ):
            raise ValueError("素材名には相対的な素材IDを指定してください")
        return value

    @validator("template")
    def valid_template(cls, value: str) -> str:
        try:
            for _, name, spec, conversion in Formatter().parse(value):
                if name is None:
                    continue
                if name not in THUMBNAIL_VARIABLES or conversion:
                    raise ValueError(f"使用できない変数です: {name}")
                if spec and not re.fullmatch(
                    r"[<^> +\-]?\d{0,3}(?:\.\d{1,2})?[sdfg]?", spec
                ):
                    raise ValueError("テンプレートの書式指定が不正です")
            value.format_map(THUMBNAIL_VARIABLES)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"テンプレートを確認してください: {exc}") from exc
        return value

    class Config:
        extra = "forbid"
        allow_inf_nan = False


class ThumbnailBackground(BaseModel):
    source: Literal["result", "image"] = "result"
    asset: str = ""
    x: int = Field(default=0, ge=-7680, le=7680)
    y: int = Field(default=0, ge=-4320, le=4320)
    scale: float = Field(default=1, ge=1, le=4)

    @validator("asset")
    def safe_asset(cls, value: str) -> str:
        return ThumbnailElement.safe_asset(value)

    class Config:
        extra = "forbid"
        allow_inf_nan = False


class ThumbnailDesign(BaseModel):
    """版付きの保存形式。初期デザイン自体は同梱JSONで管理する。"""

    version: Literal[1] = 1
    background: ThumbnailBackground = Field(
        default_factory=ThumbnailBackground
    )
    elements: list[ThumbnailElement] = Field(
        default_factory=list, max_items=64
    )

    @validator("elements")
    def unique_ids(
        cls, elements: list[ThumbnailElement]
    ) -> list[ThumbnailElement]:
        if len({e.id for e in elements}) != len(elements):
            raise ValueError("要素IDが重複しています")
        return elements

    def asset_ids(self) -> set[str]:
        """非表示要素も含め、削除から保護する素材参照。"""
        assets = {e.asset for e in self.elements if e.asset}
        assets.update(
            e.font
            for e in self.elements
            if e.source in ("text", "win_lose", "rate")
        )
        if self.background.asset:
            assets.add(self.background.asset)
        return assets

    class Config:
        extra = "forbid"


SpeechAudioEncodingLiteral = Literal["LINEAR16", "MP3", "OGG_OPUS"]


class SubtitleSpeechSettings(BaseModel):
    """字幕読み上げの設定。"""

    enabled: bool = Field(
        default=False,
        title="字幕読み上げを有効化",
        description="字幕から読み上げ音声を生成して動画に追加します",
    )
    provider: Literal["google"] = Field(
        default="google",
        title="読み上げプロバイダ",
        description="使用する読み上げサービス",
    )
    google_api_key: SecretStr = Field(
        default=SecretStr(""),
        title="Google Cloud API キー",
        description="Google Text-to-Speech API を呼び出すためのキー",
        requirement="required",
        display_level="basic",
    )
    model: str = Field(
        default="",
        title="モデル",
        description="利用する読み上げモデル。空の場合はデフォルトモデルを使用します",
    )
    voice_name: str = Field(
        default="ja-JP-Chirp3-HD-Despina",
        title="ボイス名",
        description="利用するボイスの識別子",
    )
    language_code: str = Field(
        default="ja-JP",
        title="言語コード",
        description="読み上げに使用する言語コード",
    )
    speaking_rate: float = Field(
        default=1.0,
        title="読み上げ速度",
        description="読み上げ速度倍率",
    )
    pitch: float = Field(
        default=0.0,
        title="読み上げピッチ",
        description="読み上げ音声のピッチ",
    )
    audio_encoding: SpeechAudioEncodingLiteral = Field(
        default="LINEAR16",
        title="音声エンコーディング",
        description="生成される音声データのエンコーディング形式",
    )
    sample_rate_hz: int = Field(
        default=24000,
        title="サンプルレート",
        description="生成される音声データのサンプルレート (Hz)",
    )
    track_title: str = Field(
        default="字幕読み上げ",
        title="トラックタイトル",
        description="動画に追加する音声トラックのタイトル",
    )


class VideoEditSettings(BaseModel):
    """動画編集"""

    thumbnail_design: ThumbnailDesign | None = Field(
        default=None,
        title="サムネイルデザイン",
        description="専用ダイアログで編集します",
        user_editable=True,
    )

    volume_multiplier: float = Field(
        default=1.0,
        title="音量倍率",
        description="動画の音量を調整する倍率",
    )
    title_template: str = Field(
        default="{BATTLE}({RATE}) {RULE} {WIN}勝{LOSE}敗 {DAY:'%y.%m.%d} {SCHEDULE:%H}時～",
        title="タイトルテンプレート",
        description="動画のタイトルに使用するテンプレート",
        user_editable=True,
    )
    description_template: str = Field(
        default="{CHAPTERS}",
        title="説明テンプレート",
        description="動画の説明に使用するテンプレート",
        user_editable=True,
    )
    chapter_template: str = Field(
        default="{RESULT:<5} {KILL:>3}k {DEATH:>3}d {SPECIAL:>3}s {MEDALS} {STAGE}",
        title="チャプターテンプレート",
        description="動画の説明欄に入るチャプターに使用するテンプレート",
        user_editable=True,
    )
    speech: SubtitleSpeechSettings = Field(
        default_factory=SubtitleSpeechSettings,
        title="字幕読み上げ設定",
        description="字幕読み上げ音声の生成と結合に関する設定",
    )

    class Config:
        pass
