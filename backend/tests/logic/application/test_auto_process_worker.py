from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from splat_replay.application.interfaces import (
    ConfigPort,
    EventBusPort,
    LoggerPort,
    VideoAssetRepositoryPort,
)
from splat_replay.application.services.process.auto_process_service import (
    AutoProcessService,
)
from splat_replay.application.services.system.power_manager import PowerManager
from splat_replay.application.use_cases.assets.start_edit_upload import (
    StartEditUploadUseCase,
)
from splat_replay.domain.models import VideoAsset


class _Logger:
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


class _Subscription:
    def poll(self, max_items: int | None = None) -> list[object]:
        _ = max_items
        return []

    def close(self) -> None:
        return None


class _EventBus:
    def publish_domain_event(self, event: object) -> None:
        _ = event

    def subscribe(self, event_types: set[str] | None = None) -> _Subscription:
        _ = event_types
        return _Subscription()


class _Config:
    class _Behavior:
        edit_after_power_off = True
        sleep_after_upload = False

    def get_behavior_settings(self) -> _Behavior:
        return self._Behavior()


class _Repository:
    def __init__(self, recorded: list[str]) -> None:
        self.recorded = recorded
        self.edited: list[str] = []
        self.list_recordings_calls = 0
        self.list_edited_calls = 0

    def list_recordings(self) -> list[VideoAsset]:
        self.list_recordings_calls += 1
        return [VideoAsset(video=Path(path)) for path in self.recorded]

    def list_edited(self) -> list[Path]:
        self.list_edited_calls += 1
        return [Path(path) for path in self.edited]


class _ProcessUseCase:
    def __init__(self, repo: _Repository) -> None:
        self.repo = repo
        self.execute_calls = 0
        self.completed_calls = 0
        self.fail_next = False
        self.cancel_next = False
        self.on_wait: Any = None
        self._recorded_snapshot: list[str] = []
        self._edited_snapshot: list[str] = []
        self.state = "idle"

    def is_running(self) -> bool:
        return False

    def get_state(self) -> str:
        return self.state

    async def execute(self, *, trigger: str = "manual") -> None:
        assert trigger == "auto"
        self.execute_calls += 1
        self.state = "running"
        self._recorded_snapshot = list(self.repo.recorded)
        self._edited_snapshot = list(self.repo.edited)

    async def wait_until_complete(self) -> None:
        if self.on_wait is not None:
            self.on_wait()
        if self.fail_next:
            self.fail_next = False
            self.completed_calls += 1
            self.state = "failed"
            raise RuntimeError("failed")
        if self.cancel_next:
            self.cancel_next = False
            self.completed_calls += 1
            self.state = "cancelled"
            return
        self.repo.recorded = [
            path
            for path in self.repo.recorded
            if path not in self._recorded_snapshot
        ]
        self.repo.edited = [
            path
            for path in self.repo.edited
            if path not in self._edited_snapshot
        ]
        self.completed_calls += 1
        self.state = "succeeded"


def _build_service(
    repo: _Repository, use_case: _ProcessUseCase
) -> AutoProcessService:
    return AutoProcessService(
        event_bus=cast(EventBusPort, _EventBus()),
        start_edit_upload_uc=cast(StartEditUploadUseCase, use_case),
        power_manager=cast(PowerManager, object()),
        config=cast(ConfigPort, _Config()),
        logger=cast(LoggerPort, _Logger()),
        repo=cast(VideoAssetRepositoryPort, repo),
    )


async def _wait_until(predicate: Any) -> None:
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("条件が成立しませんでした")


@pytest.mark.asyncio
async def test_startup_keeps_existing_recording_without_processing() -> None:
    repo = _Repository(["recorded/existing.mp4"])
    use_case = _ProcessUseCase(repo)
    service = _build_service(repo, use_case)
    service_task = asyncio.create_task(service.start())
    try:
        await _wait_until(lambda: service._worker_task is not None)

        assert repo.list_recordings_calls >= 1
        assert use_case.execute_calls == 0
        assert service._scan_generation == 0
        assert repo.recorded == ["recorded/existing.mp4"]
    finally:
        service_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await service_task


@pytest.mark.asyncio
async def test_startup_keeps_edited_video_without_processing() -> None:
    repo = _Repository([])
    repo.edited = ["edited/existing.mp4"]
    use_case = _ProcessUseCase(repo)
    service = _build_service(repo, use_case)
    service_task = asyncio.create_task(service.start())
    try:
        await _wait_until(lambda: service._worker_task is not None)

        assert repo.list_recordings_calls >= 1
        assert repo.list_edited_calls >= 1
        assert use_case.execute_calls == 0
        assert service._scan_generation == 0
        assert repo.edited == ["edited/existing.mp4"]
    finally:
        service_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await service_task


@pytest.mark.asyncio
async def test_scan_generation_processes_file_added_during_run_next() -> None:
    repo = _Repository(["recorded/first.mp4"])
    use_case = _ProcessUseCase(repo)
    service = _build_service(repo, use_case)

    def add_second_recording() -> None:
        if use_case.execute_calls == 1:
            repo.recorded.append("recorded/second.mp4")
            service._request_scan(delay_seconds=0.0)

    use_case.on_wait = add_second_recording
    worker = asyncio.create_task(service._run_scan_worker())
    try:
        service._request_scan(delay_seconds=0.0)
        await _wait_until(lambda: use_case.completed_calls == 2)

        assert use_case.execute_calls == 2
        assert repo.recorded == []
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker


@pytest.mark.asyncio
async def test_scan_completion_detects_added_file_without_event() -> None:
    repo = _Repository(["recorded/first.mp4"])
    use_case = _ProcessUseCase(repo)
    service = _build_service(repo, use_case)

    def add_without_notification() -> None:
        if use_case.execute_calls == 1:
            repo.recorded.append("recorded/second.mp4")

    use_case.on_wait = add_without_notification
    worker = asyncio.create_task(service._run_scan_worker())
    try:
        service._request_scan(delay_seconds=0.0)
        await _wait_until(lambda: use_case.completed_calls == 2)

        assert use_case.execute_calls == 2
        assert repo.recorded == []
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker


@pytest.mark.asyncio
async def test_cancelled_generation_does_not_cancel_later_request() -> None:
    repo = _Repository(["recorded/pending.mp4"])
    use_case = _ProcessUseCase(repo)
    service = _build_service(repo, use_case)
    service._request_scan(delay_seconds=60.0)
    service.cancel_pending_process()
    worker = asyncio.create_task(service._run_scan_worker())
    try:
        await _wait_until(
            lambda: service._handled_generation == service._scan_generation
        )
        service._request_scan(delay_seconds=0.0)
        await _wait_until(lambda: use_case.completed_calls == 1)

        assert use_case.execute_calls == 1
        assert repo.recorded == []
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker


@pytest.mark.asyncio
async def test_handled_generation_discards_superseded_deadlines() -> None:
    repo = _Repository([])
    use_case = _ProcessUseCase(repo)
    service = _build_service(repo, use_case)
    service._request_scan(delay_seconds=60.0)
    service._request_scan(delay_seconds=0.0)
    worker = asyncio.create_task(service._run_scan_worker())
    try:
        await _wait_until(
            lambda: service._handled_generation == service._scan_generation
        )

        assert service._not_before == {}
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker


@pytest.mark.asyncio
async def test_failed_residual_file_is_not_retried_in_tight_loop() -> None:
    repo = _Repository(["recorded/failing.mp4"])
    use_case = _ProcessUseCase(repo)
    use_case.fail_next = True
    service = _build_service(repo, use_case)
    worker = asyncio.create_task(service._run_scan_worker())
    try:
        service._request_scan(delay_seconds=0.0)
        await _wait_until(
            lambda: service._handled_generation == service._scan_generation
        )

        assert use_case.execute_calls == 1
        assert repo.recorded == ["recorded/failing.mp4"]
        assert service._scan_wakeup.is_set() is False
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker


@pytest.mark.asyncio
async def test_cancelled_run_waits_for_later_explicit_scan() -> None:
    repo = _Repository(["recorded/first.mp4"])
    use_case = _ProcessUseCase(repo)
    use_case.cancel_next = True
    service = _build_service(repo, use_case)

    def add_without_notification() -> None:
        if use_case.execute_calls == 1:
            repo.recorded.append("recorded/second.mp4")

    use_case.on_wait = add_without_notification
    worker = asyncio.create_task(service._run_scan_worker())
    try:
        service._request_scan(delay_seconds=0.0)
        await _wait_until(
            lambda: service._handled_generation == service._scan_generation
        )

        assert use_case.execute_calls == 1
        assert repo.recorded == [
            "recorded/first.mp4",
            "recorded/second.mp4",
        ]
        assert service._scan_wakeup.is_set() is False

        use_case.on_wait = None
        service._request_scan(delay_seconds=0.0)
        await _wait_until(lambda: use_case.completed_calls == 2)

        assert use_case.execute_calls == 2
        assert repo.recorded == []
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker
