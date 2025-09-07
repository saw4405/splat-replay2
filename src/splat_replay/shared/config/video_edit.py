from pydantic import BaseModel, Field


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

    class Config:
        pass
