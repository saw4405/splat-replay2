from pathlib import Path

from pydantic import BaseModel, Field


class VideoStorageSettings(BaseModel):
    """動画保存"""

    base_dir: Path = Field(
        default=Path("videos"),
        title="動画保存先フォルダ",
        description="動画・字幕・サムネイル・メタデータを保存するフォルダ",
    )
    keep_recordings_after_edit: bool = Field(
        default=False,
        title="編集後も元録画を保持",
        description=(
            "オン: 編集後の元録画を動画保存先/retained/recordedへ保管します。"
            "オフ: 編集完了後に削除します。Switch動画保存通知を含む録画は、"
            "ショート素材を保全するためオフでも保持します。"
        ),
        display_level="basic",
        user_editable=True,
    )
    keep_edited_after_upload: bool = Field(
        default=False,
        title="アップロード後も編集済み動画を保持",
        description=(
            "オン: アップロード後の編集済み動画を動画保存先/retained/editedへ保管します。"
            "オフ: アップロード成功後に削除します。"
        ),
        display_level="basic",
        user_editable=True,
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
    def retained_recorded_dir(self) -> Path:
        """保持した元録画を保存するフォルダ."""
        return self.base_dir / "retained" / "recorded"

    @property
    def retained_edited_dir(self) -> Path:
        """保持した編集済み動画を保存するフォルダ."""
        return self.base_dir / "retained" / "edited"

    class Config:
        pass
