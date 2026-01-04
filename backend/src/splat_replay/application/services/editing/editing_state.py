"""編集処理の状態管理。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

EditingPhase = Literal["idle", "running", "succeeded", "failed", "cancelled"]


@dataclass(frozen=True)
class EditingState:
    """編集処理の状態を表す不変オブジェクト。

    Attributes:
        phase: 処理フェーズ
        message: 状態メッセージ
        progress: 進捗率（0-100）
        current_item: 現在処理中のアイテム名
    """

    phase: EditingPhase = "idle"
    message: str = ""
    progress: int = 0
    current_item: str = ""

    def with_running(self, message: str, progress: int = 0) -> EditingState:
        """実行中状態に遷移。"""
        return replace(
            self, phase="running", message=message, progress=progress
        )

    def with_progress(
        self, progress: int, current_item: str = ""
    ) -> EditingState:
        """進捗を更新。"""
        return replace(self, progress=progress, current_item=current_item)

    def with_succeeded(self, message: str) -> EditingState:
        """成功状態に遷移。"""
        return replace(self, phase="succeeded", message=message, progress=100)

    def with_failed(self, message: str) -> EditingState:
        """失敗状態に遷移。"""
        return replace(self, phase="failed", message=message)

    def with_cancelled(self) -> EditingState:
        """キャンセル状態に遷移。"""
        return replace(
            self, phase="cancelled", message="キャンセルされました", progress=0
        )

    def with_idle(self) -> EditingState:
        """アイドル状態に遷移。"""
        return EditingState()

    @property
    def is_running(self) -> bool:
        """実行中かどうか。"""
        return self.phase == "running"
