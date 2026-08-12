from pathlib import Path

from pydantic import BaseModel, Field, SecretStr


class OBSSettings(BaseModel):
    """OBS 接続"""

    websocket_host: str = Field(
        default="localhost",
        title="OBS WebSocket ホスト",
        description="OBS WebSocket サーバーのホスト名または IP アドレス",
        user_editable=True,
    )
    websocket_port: int = Field(
        default=4455,
        title="OBS WebSocket ポート",
        description="OBS WebSocket サーバーのポート番号",
        user_editable=True,
    )
    websocket_password: SecretStr = Field(
        default=SecretStr(""),
        title="OBS WebSocket パスワード",
        description="OBS WebSocket サーバーのパスワード",
        requirement="required",
        display_level="basic",
        user_editable=True,
    )
    executable_path: Path = Field(
        default=Path("C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"),
        title="OBS 実行ファイルパス",
        description="OBS の実行ファイルのパス",
    )

    class Config:
        pass
