from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from splat_replay.domain.models import Frame, RecordingMetadata
from splat_replay.domain.services import RecordState


class SessionPhase:
    STANDBY = "standby"  # まだ matching に入っていない (ロビー等)
    MATCHING = "matching"  # マッチング中 (started_at 設定済 / バトル開始前)
    IN_GAME = "in_game"  # 録画中 (finish フラグ未検出)
    POST_FINISH = "post_finish"  # バトル終了後 判定画面待ち
    RESULT = "result"  # 結果画面表示中
    COMPLETED = "completed"  # 結果画面を抜け録画終了待ち/済


ResumeTrigger = Callable[[Frame], Awaitable[bool]]


@dataclass
class RecordingContext:
    metadata: RecordingMetadata = field(default_factory=RecordingMetadata)
    battle_started_at: float = 0.0
    finish: bool = False
    result_frame: Optional[Frame] = None
    resume_trigger: Optional[ResumeTrigger] = None
    completed: bool = False

    def reset(self) -> None:
        self.metadata.reset()
        self.battle_started_at = 0.0
        self.finish = False
        self.result_frame = None
        self.resume_trigger = None
        self.completed = False

    def phase(self, sm_state: RecordState) -> str:
        if self.result_frame is not None:
            return SessionPhase.RESULT
        if self.finish:
            return SessionPhase.POST_FINISH
        if sm_state is RecordState.RECORDING:
            return SessionPhase.IN_GAME
        if self.metadata.started_at is not None:
            return SessionPhase.MATCHING
        return SessionPhase.STANDBY
