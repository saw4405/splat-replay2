from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Awaitable, Callable, Optional

from splat_replay.domain.models import Frame, RecordingMetadata
from splat_replay.domain.services import RecordState


class SessionPhase(Enum):
    """セッションのフェーズ。"""

    STANDBY = auto()  # まだ matching に入っていない (ロビー等)
    MATCHING = auto()  # マッチング中 (started_at 設定済 / バトル開始前)
    IN_GAME = auto()  # 録画中 (finish フラグ未検出)
    POST_FINISH = auto()  # バトル終了後 判定画面待ち
    RESULT = auto()  # 結果画面表示中
    COMPLETED = auto()  # 結果画面を抜け録画終了待ち/済


ResumeTrigger = Callable[[Frame], Awaitable[bool]]


@dataclass(frozen=True)
class RecordingContext:
    """Recording session context.

    Immutable Value Object representing the state of a recording session.
    Use dataclasses.replace() for updates.
    """

    metadata: RecordingMetadata = field(default_factory=RecordingMetadata)
    manual_fields: frozenset[str] = field(default_factory=frozenset)
    pending_result_updates: dict[str, object] = field(default_factory=dict)
    battle_started_at: float = 0.0
    finish: bool = False
    result_frame: Optional[Frame] = None
    resume_trigger: Optional[ResumeTrigger] = None
    completed: bool = False
    weapon_detection_done: bool = False
    weapon_detection_attempts: int = 0
    weapon_best_scores: tuple[float, ...] | None = None
    weapon_last_visible_frame: Optional[Frame] = None

    def phase(self, sm_state: RecordState) -> SessionPhase:
        """現在のフェーズを返す。

        Args:
            sm_state: 現在の録画状態

        Returns:
            現在のセッションフェーズ
        """
        if self.result_frame is not None:
            return SessionPhase.RESULT
        if self.finish:
            return SessionPhase.POST_FINISH
        if sm_state is RecordState.RECORDING:
            return SessionPhase.IN_GAME
        if self.metadata.started_at is not None:
            return SessionPhase.MATCHING
        return SessionPhase.STANDBY
