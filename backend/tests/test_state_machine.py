"""State Machine Logic Tests.

責務：
- 状態遷移ロジックの動作を検証する
- 不正な遷移の拒否を確認する
- リスナー通知を確認する

分類: logic
"""

from __future__ import annotations

import pytest

from splat_replay.domain.services.state_machine import (
    RecordEvent,
    RecordState,
    StateMachine,
)


class TestRecordState:
    """RecordState Enum のテスト。"""

    def test_all_states_are_unique(self) -> None:
        """すべての状態が一意であることを確認。"""
        values = [state.value for state in RecordState]
        assert len(values) == len(set(values))

    def test_states_have_expected_values(self) -> None:
        """状態が期待される値を持つことを確認。"""
        assert RecordState.STOPPED.value == "stopped"
        assert RecordState.RECORDING.value == "recording"
        assert RecordState.PAUSED.value == "paused"


class TestRecordEvent:
    """RecordEvent Enum のテスト。"""

    def test_all_events_are_unique(self) -> None:
        """すべてのイベントが一意であることを確認。"""
        events = list(RecordEvent)
        assert len(events) == len(set(events))

    def test_expected_events_exist(self) -> None:
        """期待されるイベントが存在することを確認。"""
        assert RecordEvent.START in RecordEvent
        assert RecordEvent.PAUSE in RecordEvent
        assert RecordEvent.RESUME in RecordEvent
        assert RecordEvent.STOP in RecordEvent


class TestStateMachineInitialization:
    """StateMachine 初期化のテスト。"""

    def test_initial_state_is_stopped(self) -> None:
        """初期状態が STOPPED であることを確認。"""
        sm = StateMachine()
        assert sm.state == RecordState.STOPPED

    def test_initial_listeners_empty(self) -> None:
        """初期リスナーリストが空であることを確認。"""
        sm = StateMachine()
        assert sm._listeners == []


class TestStateMachineTransitions:
    """StateMachine 状態遷移のテスト。"""

    @pytest.mark.asyncio
    async def test_start_from_stopped(self) -> None:
        """STOPPED から START イベントで RECORDING に遷移する。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.START)
        assert sm.state == RecordState.RECORDING

    @pytest.mark.asyncio
    async def test_pause_from_recording(self) -> None:
        """RECORDING から PAUSE イベントで PAUSED に遷移する。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.START)
        await sm.handle(RecordEvent.PAUSE)
        assert sm.state == RecordState.PAUSED

    @pytest.mark.asyncio
    async def test_resume_from_paused(self) -> None:
        """PAUSED から RESUME イベントで RECORDING に遷移する。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.START)
        await sm.handle(RecordEvent.PAUSE)
        await sm.handle(RecordEvent.RESUME)
        assert sm.state == RecordState.RECORDING

    @pytest.mark.asyncio
    async def test_stop_from_recording(self) -> None:
        """RECORDING から STOP イベントで STOPPED に遷移する。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.START)
        await sm.handle(RecordEvent.STOP)
        assert sm.state == RecordState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_from_paused(self) -> None:
        """PAUSED から STOP イベントで STOPPED に遷移する。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.START)
        await sm.handle(RecordEvent.PAUSE)
        await sm.handle(RecordEvent.STOP)
        assert sm.state == RecordState.STOPPED


class TestStateMachineInvalidTransitions:
    """StateMachine 不正な遷移のテスト。"""

    @pytest.mark.asyncio
    async def test_pause_from_stopped_does_nothing(self) -> None:
        """STOPPED から PAUSE イベントは状態を変化させない。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.PAUSE)
        assert sm.state == RecordState.STOPPED

    @pytest.mark.asyncio
    async def test_resume_from_stopped_does_nothing(self) -> None:
        """STOPPED から RESUME イベントは状態を変化させない。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.RESUME)
        assert sm.state == RecordState.STOPPED

    @pytest.mark.asyncio
    async def test_start_from_recording_does_nothing(self) -> None:
        """RECORDING から START イベントは状態を変化させない。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.START)
        before_state = sm.state
        await sm.handle(RecordEvent.START)
        assert sm.state == before_state

    @pytest.mark.asyncio
    async def test_start_from_paused_does_nothing(self) -> None:
        """PAUSED から START イベントは状態を変化させない。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.START)
        await sm.handle(RecordEvent.PAUSE)
        before_state = sm.state
        await sm.handle(RecordEvent.START)
        assert sm.state == before_state

    @pytest.mark.asyncio
    async def test_resume_from_recording_does_nothing(self) -> None:
        """RECORDING から RESUME イベントは状態を変化させない。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.START)
        before_state = sm.state
        await sm.handle(RecordEvent.RESUME)
        assert sm.state == before_state


class TestStateMachineListeners:
    """StateMachine リスナー通知のテスト。"""

    @pytest.mark.asyncio
    async def test_listener_called_on_state_change(self) -> None:
        """状態変化時にリスナーが呼ばれることを確認。"""
        sm = StateMachine()
        called_states: list[RecordState] = []

        async def listener(state: RecordState) -> None:
            called_states.append(state)

        sm.add_listener(listener)
        await sm.handle(RecordEvent.START)

        assert called_states == [RecordState.RECORDING]

    @pytest.mark.asyncio
    async def test_listener_not_called_on_no_change(self) -> None:
        """状態が変化しない場合はリスナーが呼ばれないことを確認。"""
        sm = StateMachine()
        called_states: list[RecordState] = []

        async def listener(state: RecordState) -> None:
            called_states.append(state)

        sm.add_listener(listener)
        await sm.handle(RecordEvent.PAUSE)  # STOPPED からは遷移しない

        assert called_states == []

    @pytest.mark.asyncio
    async def test_multiple_listeners_all_called(self) -> None:
        """複数のリスナーが全て呼ばれることを確認。"""
        sm = StateMachine()
        called_states_1: list[RecordState] = []
        called_states_2: list[RecordState] = []

        async def listener1(state: RecordState) -> None:
            called_states_1.append(state)

        async def listener2(state: RecordState) -> None:
            called_states_2.append(state)

        sm.add_listener(listener1)
        sm.add_listener(listener2)
        await sm.handle(RecordEvent.START)

        assert called_states_1 == [RecordState.RECORDING]
        assert called_states_2 == [RecordState.RECORDING]

    @pytest.mark.asyncio
    async def test_listener_called_multiple_times(self) -> None:
        """複数回の状態変化でリスナーが複数回呼ばれることを確認。"""
        sm = StateMachine()
        called_states: list[RecordState] = []

        async def listener(state: RecordState) -> None:
            called_states.append(state)

        sm.add_listener(listener)
        await sm.handle(RecordEvent.START)
        await sm.handle(RecordEvent.PAUSE)
        await sm.handle(RecordEvent.RESUME)

        assert called_states == [
            RecordState.RECORDING,
            RecordState.PAUSED,
            RecordState.RECORDING,
        ]

    @pytest.mark.asyncio
    async def test_remove_listener(self) -> None:
        """リスナーを削除できることを確認。"""
        sm = StateMachine()
        called_states: list[RecordState] = []

        async def listener(state: RecordState) -> None:
            called_states.append(state)

        sm.add_listener(listener)
        await sm.handle(RecordEvent.START)
        assert len(called_states) == 1

        sm.remove_listener(listener)
        await sm.handle(RecordEvent.PAUSE)
        # リスナー削除後は呼ばれない
        assert len(called_states) == 1

    @pytest.mark.asyncio
    async def test_remove_nonexistent_listener_does_nothing(self) -> None:
        """存在しないリスナーの削除は何もしないことを確認。"""
        sm = StateMachine()

        async def listener(state: RecordState) -> None:
            pass

        # 例外が発生しないことを確認
        sm.remove_listener(listener)


class TestStateMachineComplexScenarios:
    """StateMachine 複雑なシナリオのテスト。"""

    @pytest.mark.asyncio
    async def test_full_recording_cycle(self) -> None:
        """完全な録画サイクル（開始→一時停止→再開→停止）を確認。"""
        sm = StateMachine()
        states: list[RecordState] = []

        async def listener(state: RecordState) -> None:
            states.append(state)

        sm.add_listener(listener)

        await sm.handle(RecordEvent.START)
        await sm.handle(RecordEvent.PAUSE)
        await sm.handle(RecordEvent.RESUME)
        await sm.handle(RecordEvent.STOP)

        assert states == [
            RecordState.RECORDING,
            RecordState.PAUSED,
            RecordState.RECORDING,
            RecordState.STOPPED,
        ]

    @pytest.mark.asyncio
    async def test_restart_after_stop(self) -> None:
        """停止後に再度開始できることを確認。"""
        sm = StateMachine()
        await sm.handle(RecordEvent.START)
        await sm.handle(RecordEvent.STOP)
        await sm.handle(RecordEvent.START)

        assert sm.state == RecordState.RECORDING

    @pytest.mark.asyncio
    async def test_rapid_state_changes(self) -> None:
        """連続した状態変化を正しく処理することを確認。"""
        sm = StateMachine()
        calls = 0

        async def listener(state: RecordState) -> None:
            nonlocal calls
            calls += 1

        sm.add_listener(listener)

        # 10回の状態変化
        for _ in range(5):
            await sm.handle(RecordEvent.START)
            await sm.handle(RecordEvent.STOP)

        # START と STOP が交互に発生するため、10回の変化
        assert calls == 10
