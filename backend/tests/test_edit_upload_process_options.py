from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from splat_replay.application.dto.assets import EditUploadStatusDTO
from splat_replay.application.interfaces import (
    ConfigPort,
    EventBusPort,
    LoggerPort,
    PowerPort,
    VideoAssetRepositoryPort,
)
from splat_replay.application.services.process.auto_process_service import (
    AutoProcessService,
)
from splat_replay.application.services.system.power_manager import PowerManager
from splat_replay.application.use_cases.assets.start_edit_upload import (
    StartEditUploadUseCase,
)
from splat_replay.domain.events import (
    AutoSleepPending,
    AutoSleepStarted,
    DomainEvent,
    EditUploadCompleted,
)
from splat_replay.interface.web.routers.assets import create_assets_router


@dataclass
class _BehaviorSettings:
    edit_after_power_off: bool = True
    sleep_after_upload: bool = False
    record_battle_history: bool = True


class _DummyConfig:
    def __init__(self, *, sleep_after_upload: bool) -> None:
        self._behavior = _BehaviorSettings(
            sleep_after_upload=sleep_after_upload
        )

    def get_behavior_settings(self) -> _BehaviorSettings:
        return self._behavior

    def get_upload_settings(self) -> Any:
        raise NotImplementedError

    def get_video_edit_settings(self) -> Any:
        raise NotImplementedError

    def get_obs_settings(self) -> Any:
        raise NotImplementedError

    def save_obs_websocket_password(self, password: str) -> None:
        _ = password

    def get_capture_device_settings(self) -> Any:
        raise NotImplementedError

    def save_capture_device_name(self, device_name: str) -> None:
        _ = device_name

    def save_upload_privacy_status(self, privacy_status: str) -> None:
        _ = privacy_status


class _DummyLogger:
    def debug(self, event: str, **kw: object) -> None:
        _ = event, kw

    def info(self, event: str, **kw: object) -> None:
        _ = event, kw

    def warning(self, event: str, **kw: object) -> None:
        _ = event, kw

    def error(self, event: str, **kw: object) -> None:
        _ = event, kw

    def exception(self, event: str, **kw: object) -> None:
        _ = event, kw


class _DummyEventBus:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(
        self, event_type: str, payload: dict[str, object] | None = None
    ) -> None:
        _ = event_type, payload

    def publish_domain_event(self, event: DomainEvent) -> None:
        self.events.append(event)

    def subscribe(self, event_types: set[str] | None = None) -> object:
        _ = event_types
        raise NotImplementedError


class _BlockingEditor:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def execute(self) -> None:
        self.started.set()
        await self.release.wait()

    def get_status(self) -> dict[str, object]:
        return {"progress": 0}


class _NoopUploader:
    async def execute(self) -> None:
        return None


class _PowerSpy:
    def __init__(self) -> None:
        self.sleep_calls = 0

    async def sleep(self) -> None:
        self.sleep_calls += 1


class _DummyVideoAssetRepository:
    def list_recordings(self) -> list[object]:
        return []


class _PatchStartEditUploadUseCaseStub:
    def __init__(self) -> None:
        self.updated_values: list[bool] = []

    def update_sleep_after_upload(self, enabled: bool) -> None:
        self.updated_values.append(enabled)


class _PatchGetEditUploadStatusUseCaseStub:
    def __init__(
        self, start_edit_upload_uc: _PatchStartEditUploadUseCaseStub
    ) -> None:
        self._start_edit_upload_uc = start_edit_upload_uc

    async def execute(self) -> EditUploadStatusDTO:
        latest = self._start_edit_upload_uc.updated_values[-1]
        return EditUploadStatusDTO(
            state="running",
            message="編集中です",
            progress=0,
            sleep_after_upload_default=False,
            sleep_after_upload_effective=latest,
            sleep_after_upload_overridden=latest is not False,
        )


def _build_start_use_case(
    *,
    sleep_after_upload: bool,
    editor: _BlockingEditor | None = None,
    uploader: _NoopUploader | None = None,
    event_bus: _DummyEventBus | None = None,
) -> tuple[StartEditUploadUseCase, _BlockingEditor, _DummyEventBus]:
    editor_instance = editor or _BlockingEditor()
    event_bus_instance = event_bus or _DummyEventBus()
    use_case = StartEditUploadUseCase(
        editor=cast(Any, editor_instance),
        uploader=cast(Any, uploader or _NoopUploader()),
        event_bus=cast(EventBusPort, event_bus_instance),
        config=cast(
            ConfigPort,
            _DummyConfig(sleep_after_upload=sleep_after_upload),
        ),
        logger=cast(LoggerPort, _DummyLogger()),
    )
    return use_case, editor_instance, event_bus_instance


async def _wait_for_completion(
    use_case: StartEditUploadUseCase,
) -> None:
    while use_case.is_running():
        await asyncio.sleep(0)


def _has_event(
    events: list[DomainEvent], event_type: type[DomainEvent]
) -> bool:
    return any(isinstance(event, event_type) for event in events)


def _find_event(
    events: list[DomainEvent], event_type: type[DomainEvent]
) -> DomainEvent:
    for event in events:
        if isinstance(event, event_type):
            return event
    raise AssertionError(f"{event_type.__name__} が見つかりません")


def _to_event_payload(event: DomainEvent) -> dict[str, object]:
    return {
        key: value
        for key, value in vars(event).items()
        if key
        not in {
            "event_id",
            "timestamp",
            "aggregate_id",
            "correlation_id",
        }
    }


@pytest.mark.asyncio
async def test_manual_process_override_can_enable_sleep_for_this_run_only() -> (
    None
):
    use_case, editor, event_bus = _build_start_use_case(
        sleep_after_upload=False
    )

    await use_case.execute()
    await asyncio.wait_for(editor.started.wait(), timeout=1)

    use_case.update_sleep_after_upload(True)
    editor.release.set()
    await asyncio.wait_for(_wait_for_completion(use_case), timeout=1)

    assert use_case.get_sleep_after_upload_default() is False
    assert use_case.get_sleep_after_upload_effective() is True
    assert use_case.is_sleep_after_upload_overridden() is True
    assert _has_event(event_bus.events, AutoSleepPending)


@pytest.mark.asyncio
async def test_manual_process_override_can_disable_sleep_for_this_run_only() -> (
    None
):
    use_case, editor, event_bus = _build_start_use_case(
        sleep_after_upload=True
    )

    await use_case.execute()
    await asyncio.wait_for(editor.started.wait(), timeout=1)

    use_case.update_sleep_after_upload(False)
    editor.release.set()
    await asyncio.wait_for(_wait_for_completion(use_case), timeout=1)

    assert use_case.get_sleep_after_upload_default() is True
    assert use_case.get_sleep_after_upload_effective() is False
    assert use_case.is_sleep_after_upload_overridden() is True
    assert not _has_event(event_bus.events, AutoSleepPending)


@pytest.mark.asyncio
async def test_auto_process_completion_uses_effective_sleep_setting() -> None:
    event_bus = _DummyEventBus()
    use_case, editor, _ = _build_start_use_case(
        sleep_after_upload=False,
        event_bus=event_bus,
    )
    power_manager = PowerManager(
        power=cast(PowerPort, _PowerSpy()),
        config=cast(
            ConfigPort,
            _DummyConfig(sleep_after_upload=False),
        ),
        logger=cast(LoggerPort, _DummyLogger()),
    )
    service = AutoProcessService(
        event_bus=cast(EventBusPort, event_bus),
        start_edit_upload_uc=use_case,
        power_manager=power_manager,
        config=cast(
            ConfigPort,
            _DummyConfig(sleep_after_upload=False),
        ),
        logger=cast(LoggerPort, _DummyLogger()),
        repo=cast(VideoAssetRepositoryPort, _DummyVideoAssetRepository()),
    )

    await use_case.execute(trigger="auto")
    await asyncio.wait_for(editor.started.wait(), timeout=1)

    use_case.update_sleep_after_upload(True)
    editor.release.set()
    await asyncio.wait_for(_wait_for_completion(use_case), timeout=1)
    completed_event = cast(
        EditUploadCompleted,
        _find_event(event_bus.events, EditUploadCompleted),
    )
    await use_case.execute(trigger="auto")
    await asyncio.wait_for(editor.started.wait(), timeout=1)
    await service.handle_edit_upload_completed(
        SimpleNamespace(payload=_to_event_payload(completed_event))
    )

    assert _has_event(event_bus.events, AutoSleepPending)


@pytest.mark.asyncio
async def test_start_auto_sleep_executes_power_sleep_when_runtime_override_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_bus = _DummyEventBus()
    use_case, editor, _ = _build_start_use_case(
        sleep_after_upload=False,
        event_bus=event_bus,
    )
    power = _PowerSpy()
    power_manager = PowerManager(
        power=cast(PowerPort, power),
        config=cast(
            ConfigPort,
            _DummyConfig(sleep_after_upload=False),
        ),
        logger=cast(LoggerPort, _DummyLogger()),
    )
    service = AutoProcessService(
        event_bus=cast(EventBusPort, event_bus),
        start_edit_upload_uc=use_case,
        power_manager=power_manager,
        config=cast(
            ConfigPort,
            _DummyConfig(sleep_after_upload=False),
        ),
        logger=cast(LoggerPort, _DummyLogger()),
        repo=cast(VideoAssetRepositoryPort, _DummyVideoAssetRepository()),
    )

    async def _no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "splat_replay.application.services.process.auto_process_service.asyncio.sleep",
        _no_wait,
    )

    await use_case.execute()
    await asyncio.wait_for(editor.started.wait(), timeout=1)

    use_case.update_sleep_after_upload(True)
    editor.release.set()
    await asyncio.wait_for(_wait_for_completion(use_case), timeout=1)
    completed_event = cast(
        EditUploadCompleted,
        _find_event(event_bus.events, EditUploadCompleted),
    )
    await service.handle_edit_upload_completed(
        SimpleNamespace(payload=_to_event_payload(completed_event))
    )
    await use_case.execute()
    await asyncio.wait_for(_wait_for_completion(use_case), timeout=1)
    await service.start_auto_sleep()

    assert power.sleep_calls == 1
    assert _has_event(event_bus.events, AutoSleepStarted)


def test_update_edit_upload_process_options_returns_200_with_updated_status() -> (
    None
):
    start_edit_upload_uc = _PatchStartEditUploadUseCaseStub()
    get_edit_upload_status_uc = _PatchGetEditUploadStatusUseCaseStub(
        start_edit_upload_uc
    )
    app = FastAPI()
    app.include_router(
        create_assets_router(
            cast(
                Any,
                SimpleNamespace(
                    start_edit_upload_uc=start_edit_upload_uc,
                    get_edit_upload_status_uc=get_edit_upload_status_uc,
                ),
            )
        )
    )

    with TestClient(app) as client:
        response = client.patch(
            "/api/process/edit-upload/options",
            json={"sleep_after_upload": True},
        )

    assert response.status_code == 200
    assert start_edit_upload_uc.updated_values == [True]
    assert response.json() == {
        "state": "running",
        "started_at": None,
        "finished_at": None,
        "error": None,
        "sleep_after_upload_default": False,
        "sleep_after_upload_effective": True,
        "sleep_after_upload_overridden": True,
    }


def test_update_edit_upload_process_options_returns_409_when_not_running(
    client: TestClient,
) -> None:
    response = client.patch(
        "/api/process/edit-upload/options",
        json={"sleep_after_upload": True},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "編集中またはアップロード中の処理がないため変更できません"
    )
