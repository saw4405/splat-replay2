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

    class Config:
        pass
