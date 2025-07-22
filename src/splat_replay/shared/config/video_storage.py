from pathlib import Path

from pydantic import BaseModel


class VideoStorageSettings(BaseModel):
    """動画ファイルを保存するフォルダ設定。"""
    base_dir: Path = Path("videos")

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
