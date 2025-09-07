from pydantic import BaseModel, Field


class BehaviorSettings(BaseModel):
    """動作"""

    edit_after_power_off: bool = Field(
        default=True,
        title="電源オフ後に編集開始する",
        description="Switchの電源オフ後に自動的に編集・アップロード処理を開始するかどうか",
        recommended=False,
    )
    sleep_after_upload: bool = Field(
        default=False,
        title="アップロード終了後にスリープする",
        description="アップロード終了後にPCをスリープさせるかどうか",
        recommended=False,
    )

    class Config:
        pass
