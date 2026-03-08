from pathlib import Path

from pydantic import BaseModel, Field


class VideoStorageSettings(BaseModel):
    """動画保存"""

    base_dir: Path = Field(
        default=Path("videos"),
        title="動画保存先フォルダ",
        description="動画・字幕・サムネイル・メタデータを保存するフォルダ",
        recommended=False,
    )

    @property
    def recorded_dir(self) -> Path:
        """録画済み動画を保存するフォルダ."""
        return self.base_dir / "recorded"

    @property
    def edited_dir(self) -> Path:
        """編集済み動画を保存するフォルダ."""
        return self.base_dir / "edited"

    @property
    def history_dir(self) -> Path:
        """対戦履歴を保存するフォルダ."""
        return self.base_dir / "history"

    @property
    def battle_history_file(self) -> Path:
        """対戦履歴ファイル."""
        return self.history_dir / "battle_history.json"

    class Config:
        pass
