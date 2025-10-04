"""Web API のレスポンスモデル定義。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CommandResultModel(BaseModel):
    """コマンド実行結果を表す共通レスポンス。"""

    ok: bool = Field(..., description="コマンドが成功した場合に True。")
    error: str | None = Field(
        None, description="失敗時のエラーメッセージ。成功時は null。"
    )


class AssetEditedDirResponseModel(CommandResultModel):
    """編集済み動画ディレクトリのパスを返すレスポンス。"""

    path: str | None = Field(
        None,
        description=(
            "編集済み動画を格納するディレクトリの絶対パス。成功時のみ有効"
        ),
    )


class AutoRecorderStartResponseModel(CommandResultModel):
    """自動録画開始リクエストの結果を表すレスポンス。"""

    message: str | None = Field(
        None,
        description="クライアントへ表示するステータスメッセージ。",
    )
    waiting_for_device: bool = Field(
        False,
        description="キャプチャデバイス接続待機中であれば True。",
    )


__all__ = [
    "AssetEditedDirResponseModel",
    "AutoRecorderStartResponseModel",
    "CommandResultModel",
]
