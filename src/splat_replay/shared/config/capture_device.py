from pydantic import BaseModel


class CaptureDeviceSettings(BaseModel):
    """OBS のキャプチャデバイス設定。"""

    name: str = "Capture Device"

    class Config:
        pass
