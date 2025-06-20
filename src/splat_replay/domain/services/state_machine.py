"""バトル進行を管理する簡易ステートマシン。"""

from __future__ import annotations

from enum import Enum, auto

from splat_replay.shared.logger import get_logger

logger = get_logger()


class State(Enum):
    """バトルの状態および起動直後の状態。"""

    READINESS_CHECK = auto()
    STANDBY = auto()
    RECORDING = auto()
    PAUSED = auto()


class Event(Enum):
    """状態変化イベント。"""

    INITIALIZED = auto()
    BATTLE_STARTED = auto()
    LOADING_DETECTED = auto()
    LOADING_FINISHED = auto()
    POSTGAME_DETECTED = auto()
    EARLY_ABORT = auto()
    MANUAL_PAUSE = auto()
    MANUAL_RESUME = auto()


TRANSITIONS: dict[tuple[State, Event], State] = {
    (State.READINESS_CHECK, Event.INITIALIZED): State.STANDBY,
    (State.STANDBY, Event.BATTLE_STARTED): State.RECORDING,
    (State.RECORDING, Event.LOADING_DETECTED): State.PAUSED,
    (State.PAUSED, Event.LOADING_FINISHED): State.RECORDING,
    (State.RECORDING, Event.MANUAL_PAUSE): State.PAUSED,
    (State.PAUSED, Event.MANUAL_RESUME): State.RECORDING,
    (State.RECORDING, Event.POSTGAME_DETECTED): State.STANDBY,
    (State.RECORDING, Event.EARLY_ABORT): State.STANDBY,
}


class StateMachine:
    """状態を遷移させつつログ出力する。"""

    def __init__(self) -> None:
        self.state = State.READINESS_CHECK
        logger.info("state=%s", self.state.name)

    def handle(self, event: Event) -> None:
        before = self.state
        self.state = TRANSITIONS.get((self.state, event), self.state)
        if self.state != before:
            logger.info("event=%s state=%s", event.name, self.state.name)
