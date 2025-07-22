from pathlib import Path

from pydantic import BaseModel


class OBSSettings(BaseModel):
    """OBS 接続設定。"""
    websocket_host: str = "localhost"
    websocket_port: int = 4455
    websocket_password: str = ""
    executable_path: Path = Path(
        "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe")

    class Config:
        pass
