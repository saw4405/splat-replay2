from pydantic import BaseModel, Field


class CaptureDeviceSettings(BaseModel):
    """キャプチャボード"""

    name: str = Field(
        default="Capture Device",
        title="キャプチャボード名",
        description="OSが認識しているキャプチャボードの名称",
        recommended=True,
    )

    class Config:
        pass
