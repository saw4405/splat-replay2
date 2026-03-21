from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, Field, validator

WebViewRenderMode = Literal["cpu", "gpu"]


class WebViewSettings(BaseModel):
    """表示"""

    render_mode: WebViewRenderMode = Field(
        default="gpu",
        title="描画モード",
        description=(
            "CPU: プレビュー表示はややカクつきますが、OBSの録画は安定しやすい設定です。 "
            "GPU: プレビュー表示は滑らかですが、GPU負荷が高くなり、OBSの録画結果に影響する場合があります。 "
            "プレビュー更新頻度の変更は保存後すぐに反映されます。 "
            "描画モードの切り替えは再起動後に反映されます。"
        ),
        choices=["cpu", "gpu"],
        choice_labels={"cpu": "CPU", "gpu": "GPU"},
        recommended=False,
        user_editable=True,
    )

    @validator("render_mode", pre=True, always=True)
    def normalize_render_mode(cls, value: object) -> WebViewRenderMode:
        if isinstance(value, str):
            normalized = value.lower()
            if normalized in {"cpu", "gpu"}:
                return cast(WebViewRenderMode, normalized)
        return "gpu"

    class Config:
        pass
