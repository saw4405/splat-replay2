from pathlib import Path

from pydantic import BaseModel, Field, SecretStr


class OBSSettings(BaseModel):
    """OBS 接続"""

    websocket_host: str = Field(
        default="localhost",
        title="OBS WebSocket ホスト",
        description="OBS WebSocket サーバーのホスト名または IP アドレス",
        recommended=False,
    )
    websocket_port: int = Field(
        default=4455,
        title="OBS WebSocket ポート",
        description="OBS WebSocket サーバーのポート番号",
        recommended=False,
    )
    websocket_password: SecretStr = Field(
        default=SecretStr(""),
        title="OBS WebSocket パスワード",
        description="OBS WebSocket サーバーのパスワード",
        recommended=True,
    )
    executable_path: Path = Field(
        default=Path("C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"),
        title="OBS 実行ファイルパス",
        description="OBS の実行ファイルのパス",
        recommended=False,
    )

    class Config:
        pass
