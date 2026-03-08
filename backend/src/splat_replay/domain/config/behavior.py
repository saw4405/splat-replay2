from pydantic import BaseModel, Field


class BehaviorSettings(BaseModel):
    """動作"""

    edit_after_power_off: bool = Field(
        default=True,
        title="電源オフ後に編集開始する",
        description="Switchの電源オフ後に自動的に編集・アップロード処理を開始するかどうか",
        recommended=False,
        user_editable=True,
    )
    sleep_after_upload: bool = Field(
        default=False,
        title="アップロード終了後にスリープする",
        description="アップロード終了後にPCをスリープさせるかどうか",
        recommended=False,
        user_editable=True,
    )
    record_battle_history: bool = Field(
        default=True,
        title="対戦履歴を累積記録する",
        description=(
            "ブキ判別結果と対戦メタデータを集計用の履歴として累積保存するかどうか"
        ),
        recommended=True,
        user_editable=True,
    )

    class Config:
        pass
