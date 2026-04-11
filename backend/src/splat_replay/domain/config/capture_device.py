from pydantic import BaseModel, Field


class CaptureDeviceSettings(BaseModel):
    """Capture device settings."""

    name: str = Field(
        default="Capture Device",
        title="キャプチャデバイス名",
        description="OSに登録されているキャプチャデバイスの表示名",
        recommended=True,
        user_editable=True,
    )
    hardware_id: str | None = Field(
        default=None,
        title="ハードウェア ID",
        description="復旧用に自動取得されるデバイス識別子",
        recommended=False,
        user_editable=False,
    )
    location_path: str | None = Field(
        default=None,
        title="ロケーション パス",
        description="復旧用に自動取得される接続ポート識別子",
        recommended=False,
        user_editable=False,
    )
    parent_instance_id: str | None = Field(
        default=None,
        title="親インスタンス ID",
        description="復旧用に自動取得される親 PnP デバイス ID",
        recommended=False,
        user_editable=False,
    )

    class Config:
        pass
