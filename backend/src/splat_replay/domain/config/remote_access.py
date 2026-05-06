from __future__ import annotations

from pydantic import BaseModel, Field


class RemoteAccessSettings(BaseModel):
    """LAN アクセス"""

    enabled: bool = Field(
        default=False,
        title="LAN 公開",
        description=(
            "家庭内LANからスマホでPCと同じ画面を開けるようにします。"
            "有効化後はアプリを再起動すると反映されます。"
            "無認証のため、信頼できる家庭内ネットワークでだけ使用してください。"
        ),
        recommended=False,
        user_editable=True,
    )

    class Config:
        pass
