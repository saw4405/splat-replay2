from typing import List, Literal

from pydantic import BaseModel, Field


class UploadSettings(BaseModel):
    """アップロード"""

    privacy_status: Literal["public", "unlisted", "private"] = Field(
        default="private",
        title="公開範囲",
        description="動画の公開範囲",
        recommended=False,
        choices=["public", "unlisted", "private"],
        user_editable=True,
    )
    tags: List[str] = Field(
        default=[],
        title="タグ",
        description="動画に付与するタグ",
        recommended=False,
        user_editable=True,
    )
    playlist_id: str = Field(
        default="",
        title="プレイリストID",
        description="動画を追加するプレイリストのID\nプレイリストに追加しない場合は空欄",
        recommended=False,
        user_editable=True,
    )
    caption_name: str = Field(
        default="ひとりごと",
        title="キャプション名",
        description="動画のキャプションに使用する名前",
        recommended=False,
        user_editable=True,
    )

    class Config:
        pass
