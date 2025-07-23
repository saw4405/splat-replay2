"""バトル進行を管理する簡易ステートマシン。"""

from __future__ import annotations

from enum import Enum, auto
from typing import Callable

from structlog.stdlib import BoundLogger


class State(Enum):
    """アプリ全体の状態。"""

    WAITING_DEVICE = auto()
    OBS_STARTING = auto()
    STANDBY = auto()
    RECORDING = auto()
    PAUSED = auto()
    EDITING = auto()
    UPLOADING = auto()
    SLEEPING = auto()


class Event(Enum):
    """状態変化イベント。"""

    DEVICE_CONNECTED = auto()
    INITIALIZED = auto()
    MANUAL_START = auto()
    BATTLE_STARTED = auto()
    LOADING_DETECTED = auto()
    LOADING_FINISHED = auto()
    EARLY_ABORT = auto()
    TIME_OUT = auto()
    BATTLE_ENDED = auto()
    MANUAL_PAUSE = auto()
    MANUAL_RESUME = auto()
    MANUAL_STOP = auto()
    EDIT_START = auto()
    EDIT_END = auto()
    UPLOAD_START = auto()
    UPLOAD_END = auto()
    SLEEP = auto()


TRANSITIONS: dict[tuple[State, Event], State] = {
    (State.WAITING_DEVICE, Event.DEVICE_CONNECTED): State.OBS_STARTING,
    (State.OBS_STARTING, Event.INITIALIZED): State.STANDBY,
    (State.STANDBY, Event.BATTLE_STARTED): State.RECORDING,
    (State.STANDBY, Event.MANUAL_START): State.RECORDING,
    (State.RECORDING, Event.LOADING_DETECTED): State.PAUSED,
    (State.PAUSED, Event.LOADING_FINISHED): State.RECORDING,
    (State.RECORDING, Event.MANUAL_PAUSE): State.PAUSED,
    (State.PAUSED, Event.MANUAL_RESUME): State.RECORDING,
    (State.RECORDING, Event.EARLY_ABORT): State.STANDBY,
    (State.RECORDING, Event.TIME_OUT): State.STANDBY,
    (State.RECORDING, Event.BATTLE_ENDED): State.STANDBY,
    (State.RECORDING, Event.MANUAL_STOP): State.STANDBY,
    (State.PAUSED, Event.MANUAL_STOP): State.STANDBY,
    (State.STANDBY, Event.EDIT_START): State.EDITING,
    (State.EDITING, Event.EDIT_END): State.STANDBY,
    (State.STANDBY, Event.UPLOAD_START): State.UPLOADING,
    (State.UPLOADING, Event.UPLOAD_END): State.STANDBY,
    (State.STANDBY, Event.SLEEP): State.SLEEPING,
}


class StateMachine:
    """状態を遷移させつつ通知する。"""

    def __init__(self, logger: BoundLogger) -> None:
        self.state = State.WAITING_DEVICE
        self._listeners: list[Callable[[State], None]] = []
        self.logger = logger
        self.logger.info("state=%s", self.state.name)

    def add_listener(self, func: Callable[[State], None]) -> None:
        """状態変化リスナーを登録する。"""
        self._listeners.append(func)

    def remove_listener(self, func: Callable[[State], None]) -> None:
        """状態変化リスナーを解除する。"""
        if func in self._listeners:
            self._listeners.remove(func)

    def handle(self, event: Event) -> None:
        before = self.state
        self.state = TRANSITIONS.get((self.state, event), self.state)
        if self.state != before:
            self.logger.info("event=%s state=%s", event.name, self.state.name)
            for cb in list(self._listeners):
                cb(self.state)
