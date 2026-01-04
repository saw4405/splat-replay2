"""バトル進行を管理する簡易ステートマシン。"""

from __future__ import annotations

from enum import Enum, auto
from typing import Awaitable, Callable, Dict, Tuple


class RecordState(Enum):
    """録画状態を表す列挙型。"""

    STOPPED = "stopped"
    RECORDING = "recording"
    PAUSED = "paused"


class RecordEvent(Enum):
    """録画状態変化イベント。"""

    START = auto()
    PAUSE = auto()
    RESUME = auto()
    STOP = auto()


RECORD_TRANSITIONS: Dict[Tuple[RecordState, RecordEvent], RecordState] = {
    (RecordState.STOPPED, RecordEvent.START): RecordState.RECORDING,
    (RecordState.RECORDING, RecordEvent.PAUSE): RecordState.PAUSED,
    (RecordState.PAUSED, RecordEvent.RESUME): RecordState.RECORDING,
    (RecordState.RECORDING, RecordEvent.STOP): RecordState.STOPPED,
    (RecordState.PAUSED, RecordEvent.STOP): RecordState.STOPPED,
}


class StateMachine:
    """状態を遷移させつつ通知する。"""

    def __init__(self) -> None:
        self.state = RecordState.STOPPED
        self._listeners: list[Callable[[RecordState], Awaitable[None]]] = []

    def add_listener(
        self, listener: Callable[[RecordState], Awaitable[None]]
    ) -> None:
        """状態変化リスナーを登録する。"""
        self._listeners.append(listener)

    def remove_listener(
        self, listener: Callable[[RecordState], Awaitable[None]]
    ) -> None:
        """状態変化リスナーを解除する。"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def handle(self, event: RecordEvent) -> None:
        before_state = self.state
        self.state = RECORD_TRANSITIONS.get((self.state, event), self.state)
        if self.state != before_state:
            for cb in list(self._listeners):
                await cb(self.state)
