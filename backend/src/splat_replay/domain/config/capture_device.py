from pydantic import BaseModel, Field


class CaptureDeviceSettings(BaseModel):
    """Capture device settings."""

    name: str = Field(
        default="Capture Device",
        title="キャプチャデバイス名",
        description="OSに登録されているキャプチャデバイスの表示名",
        requirement="required",
        display_level="basic",
        user_editable=True,
    )

    class Config:
        pass
