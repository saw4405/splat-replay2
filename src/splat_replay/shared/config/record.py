from pydantic import BaseModel


class RecordSettings(BaseModel):
    """録画関連の設定。"""
    capture_index: int = 0
    width: int = 1920
    height: int = 1080

    class Config:
        pass
