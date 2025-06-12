from __future__ import annotations

from splat_replay.domain.services.state_machine import (
    Event,
    State,
    StateMachine,
)


def test_state_transitions() -> None:
    sm = StateMachine()
    assert sm.state is State.STANDBY

    sm.handle(Event.BATTLE_STARTED)
    assert sm.state is State.RECORDING

    sm.handle(Event.LOADING_DETECTED)
    assert sm.state is State.PAUSED

    sm.handle(Event.LOADING_FINISHED)
    assert sm.state is State.RECORDING

    sm.handle(Event.POSTGAME_DETECTED)
    assert sm.state is State.STANDBY
