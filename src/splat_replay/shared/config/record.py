from pydantic import BaseModel, Field


class RecordSettings(BaseModel):
    """録画"""

    capture_device: str = Field(
        default="OBS Virtual Camera",
        title="キャプチャデバイス",
        description="OBSの仮想カメラが出力されているキャプチャデバイス名、もしくはインデックス。通常、0がPC標準カメラ、1がキャプチャボード、2がOBSの仮想カメラです",
        recommended=True,
    )
    width: int = Field(
        default=1920,
        title="録画する映像の幅",
        description="",
        recommended=False,
    )
    height: int = Field(
        default=1080,
        title="録画する映像の高さ",
        description="",
        recommended=False,
    )

    class Config:
        pass
