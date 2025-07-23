from pydantic import BaseModel


class PCSettings(BaseModel):
    """PC固有の設定。"""

    sleep_after_finish: bool = True

    class Config:
        pass
