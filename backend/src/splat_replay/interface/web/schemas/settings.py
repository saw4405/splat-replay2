"""Settings-related schemas for Web API.

設定機能に関するリクエスト/レスポンス スキーマを定義する。
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel

__all__ = [
    "SettingsUpdateSection",
    "SettingsUpdateRequest",
]


class SettingsUpdateSection(BaseModel):
    """設定更新セクション。PyInstallerでの循環参照を避けるためAnyを使用。"""

    id: str
    values: Dict[str, Any]  # FieldValueは再帰的型定義のためAnyに置換


class SettingsUpdateRequest(BaseModel):
    """設定更新リクエスト"""

    sections: List[SettingsUpdateSection]
