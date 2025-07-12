"""バトル進行を管理する簡易ステートマシン。"""

from __future__ import annotations

from enum import Enum, auto
from typing import Callable

from splat_replay.shared.logger import get_logger

logger = get_logger()


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
    BATTLE_STARTED = auto()
    LOADING_DETECTED = auto()
    LOADING_FINISHED = auto()
    POSTGAME_DETECTED = auto()
    EARLY_ABORT = auto()
    MANUAL_PAUSE = auto()
    MANUAL_RESUME = auto()
    EDIT_START = auto()
    EDIT_END = auto()
    UPLOAD_START = auto()
    UPLOAD_END = auto()
    SLEEP = auto()


TRANSITIONS: dict[tuple[State, Event], State] = {
    (State.WAITING_DEVICE, Event.DEVICE_CONNECTED): State.OBS_STARTING,
    (State.OBS_STARTING, Event.INITIALIZED): State.STANDBY,
    (State.STANDBY, Event.BATTLE_STARTED): State.RECORDING,
    (State.RECORDING, Event.LOADING_DETECTED): State.PAUSED,
    (State.PAUSED, Event.LOADING_FINISHED): State.RECORDING,
    (State.RECORDING, Event.MANUAL_PAUSE): State.PAUSED,
    (State.PAUSED, Event.MANUAL_RESUME): State.RECORDING,
    (State.RECORDING, Event.POSTGAME_DETECTED): State.STANDBY,
    (State.RECORDING, Event.EARLY_ABORT): State.STANDBY,
    (State.STANDBY, Event.EDIT_START): State.EDITING,
    (State.EDITING, Event.EDIT_END): State.STANDBY,
    (State.STANDBY, Event.UPLOAD_START): State.UPLOADING,
    (State.UPLOADING, Event.UPLOAD_END): State.STANDBY,
    (State.STANDBY, Event.SLEEP): State.SLEEPING,
}


class StateMachine:
    """状態を遷移させつつ通知する。"""

    def __init__(self) -> None:
        self.state = State.WAITING_DEVICE
        self._listeners: list[Callable[[State], None]] = []
        logger.info("state=%s", self.state.name)

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
            logger.info("event=%s state=%s", event.name, self.state.name)
            for cb in list(self._listeners):
                cb(self.state)
