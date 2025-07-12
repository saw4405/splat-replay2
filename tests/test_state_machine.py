from __future__ import annotations

from splat_replay.domain.services.state_machine import (
    Event,
    State,
    StateMachine,
)


def test_state_transitions() -> None:
    sm = StateMachine()
    assert sm.state is State.WAITING_DEVICE

    sm.handle(Event.DEVICE_CONNECTED)
    assert sm.state is State.OBS_STARTING

    sm.handle(Event.INITIALIZED)
    assert sm.state is State.STANDBY

    sm.handle(Event.BATTLE_STARTED)
    assert sm.state is State.RECORDING

    sm.handle(Event.LOADING_DETECTED)
    assert sm.state is State.PAUSED

    sm.handle(Event.LOADING_FINISHED)
    assert sm.state is State.RECORDING

    sm.handle(Event.POSTGAME_DETECTED)
    assert sm.state is State.STANDBY

    sm.handle(Event.EDIT_START)
    assert sm.state is State.EDITING

    sm.handle(Event.EDIT_END)
    assert sm.state is State.STANDBY

    sm.handle(Event.UPLOAD_START)
    assert sm.state is State.UPLOADING

    sm.handle(Event.UPLOAD_END)
    assert sm.state is State.STANDBY

    sm.handle(Event.SLEEP)
    assert sm.state is State.SLEEPING


def test_manual_pause_resume() -> None:
    sm = StateMachine()

    sm.handle(Event.DEVICE_CONNECTED)
    sm.handle(Event.INITIALIZED)

    sm.handle(Event.BATTLE_STARTED)
    assert sm.state is State.RECORDING

    sm.handle(Event.MANUAL_PAUSE)
    assert sm.state is State.PAUSED

    sm.handle(Event.MANUAL_RESUME)
    assert sm.state is State.RECORDING


def test_state_listener() -> None:
    sm = StateMachine()
    history: list[State] = []

    def _listener(state: State) -> None:
        history.append(state)

    sm.add_listener(_listener)
    sm.handle(Event.DEVICE_CONNECTED)
    assert history[-1] is State.OBS_STARTING
