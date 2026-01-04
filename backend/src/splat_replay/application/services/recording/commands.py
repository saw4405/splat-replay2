"""Recording commands - 録画制御のコマンド定義。

Phase 4 リファクタリング: Handler が副作用ではなく意図（Command）を返すようにする。
これにより Handler を純粋関数に近づけ、テスタビリティと保守性を向上。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from splat_replay.application.services.recording.recording_context import (
        RecordingContext,
    )


class RecordingAction(Enum):
    """録画制御アクション。

    Note:
        NONE = 状態変化なし（Context の更新のみ）
    """

    # 録画制御
    START_RECORDING = auto()
    PAUSE_RECORDING = auto()
    RESUME_RECORDING = auto()
    STOP_RECORDING = auto()
    CANCEL_RECORDING = auto()

    # メタデータ制御
    RESET_METADATA = auto()

    # 何もしない（Context 更新のみ）
    NONE = auto()


@dataclass(frozen=True)
class RecordingCommand:
    """録画制御コマンド。

    Handler の処理結果を表現する値オブジェクト。
    - action: 実行すべき副作用（録画開始/停止等）
    - updated_context: フレーム処理後の新しい Context
    - reason: コマンド発行理由（デバッグ/ログ用）

    設計方針:
        Command と Context を分離することで、責務を明確化。
        Handler は「判断」のみ、UseCase が「実行」と「Context 管理」を担当。
    """

    action: RecordingAction
    updated_context: RecordingContext
    reason: str = ""

    @staticmethod
    def none(updated_context: RecordingContext) -> RecordingCommand:
        """状態変化なしコマンド（Context 更新のみ）。"""
        return RecordingCommand(RecordingAction.NONE, updated_context, "")

    @staticmethod
    def start_recording(
        updated_context: RecordingContext, reason: str = ""
    ) -> RecordingCommand:
        """録画開始コマンドを作成。"""
        return RecordingCommand(
            RecordingAction.START_RECORDING, updated_context, reason
        )

    @staticmethod
    def pause_recording(
        updated_context: RecordingContext, reason: str = ""
    ) -> RecordingCommand:
        """録画一時停止コマンドを作成。"""
        return RecordingCommand(
            RecordingAction.PAUSE_RECORDING, updated_context, reason
        )

    @staticmethod
    def resume_recording(
        updated_context: RecordingContext, reason: str = ""
    ) -> RecordingCommand:
        """録画再開コマンドを作成。"""
        return RecordingCommand(
            RecordingAction.RESUME_RECORDING, updated_context, reason
        )

    @staticmethod
    def stop_recording(
        updated_context: RecordingContext, reason: str = ""
    ) -> RecordingCommand:
        """録画停止コマンドを作成。"""
        return RecordingCommand(
            RecordingAction.STOP_RECORDING, updated_context, reason
        )

    @staticmethod
    def cancel_recording(
        updated_context: RecordingContext, reason: str = ""
    ) -> RecordingCommand:
        """録画キャンセルコマンドを作成。"""
        return RecordingCommand(
            RecordingAction.CANCEL_RECORDING, updated_context, reason
        )

    @staticmethod
    def reset_metadata(
        updated_context: RecordingContext, reason: str = ""
    ) -> RecordingCommand:
        """メタデータリセットコマンドを作成。"""
        return RecordingCommand(
            RecordingAction.RESET_METADATA, updated_context, reason
        )
