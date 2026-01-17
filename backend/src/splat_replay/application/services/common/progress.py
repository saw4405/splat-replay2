"""Progress event bus and reporter.

AutoEditor / AutoUploader publish progress to GUI via EventPublisher.
Threading model: events are dispatched to listeners; GUI controller bridges to Tk.
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from typing import List, Optional, Protocol, Union

from splat_replay.application.interfaces import (
    EventBusPort,
    EventPublisher,
    LoggerPort,
)


@dataclass(slots=True)
class ProgressEvent:
    task_id: str
    kind: str  # start | total | stage | advance | finish | items | item_stage | item_finish
    task_name: str
    total: Optional[int] = None
    completed: Optional[int] = None
    stage_key: Optional[str] = None
    stage_label: Optional[str] = None
    stage_index: Optional[int] = None
    stage_count: Optional[int] = None
    success: Optional[bool] = None
    message: Optional[str] = None
    # structured itemized progress
    items: Optional[List[str]] = None
    item_index: Optional[int] = None
    item_key: Optional[str] = None
    item_label: Optional[str] = None


class ProgressListener(Protocol):
    """Progress event listener (sync or async)."""

    def __call__(
        self, event: ProgressEvent
    ) -> Union[None, Awaitable[None]]: ...


class ProgressReporter:
    """Progress publisher with simple and structured APIs."""

    def __init__(self, publisher: EventPublisher, logger: LoggerPort) -> None:
        self._listeners: List[ProgressListener] = []
        self._totals: dict[str, Optional[int]] = {}
        self._completed: dict[str, int] = {}
        self._publisher = publisher
        self._logger = logger

    # listeners
    def add_listener(self, listener: ProgressListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: ProgressListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    # simple API
    def start_task(
        self,
        task_id: str,
        task_name: str,
        total: Optional[int],
        items: Optional[List[str]] = None,
    ) -> None:
        self._totals[task_id] = total
        self._completed[task_id] = 0
        self._emit(
            ProgressEvent(
                task_id=task_id,
                kind="start",
                task_name=task_name,
                total=total,
                completed=0,
                items=list(items) if items is not None else None,
            )
        )

    def update_total(self, task_id: str, total: int) -> None:
        self._totals[task_id] = total
        self._emit(
            ProgressEvent(
                task_id=task_id,
                kind="total",
                task_name="",
                total=total,
                completed=self._completed.get(task_id),
            )
        )

    def stage(
        self,
        task_id: str,
        stage_key: str,
        stage_label: str,
        *,
        index: Optional[int] = None,
        count: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        self._emit(
            ProgressEvent(
                task_id=task_id,
                kind="stage",
                task_name="",
                total=self._totals.get(task_id),
                completed=self._completed.get(task_id),
                stage_key=stage_key,
                stage_label=stage_label,
                stage_index=index,
                stage_count=count,
                message=message,
            )
        )

    def advance(self, task_id: str, inc: int = 1) -> None:
        self._completed[task_id] = self._completed.get(task_id, 0) + inc
        self._emit(
            ProgressEvent(
                task_id=task_id,
                kind="advance",
                task_name="",
                total=self._totals.get(task_id),
                completed=self._completed[task_id],
            )
        )

    def finish(
        self, task_id: str, success: bool = True, message: str | None = None
    ) -> None:
        self._emit(
            ProgressEvent(
                task_id=task_id,
                kind="finish",
                task_name="",
                total=self._totals.get(task_id),
                completed=self._completed.get(task_id),
                success=success,
                message=message,
            )
        )

    # structured API
    def init_items(self, task_id: str, items: List[str]) -> None:
        self._emit(
            ProgressEvent(
                task_id=task_id,
                kind="items",
                task_name="",
                items=list(items),
                total=self._totals.get(task_id),
                completed=self._completed.get(task_id),
            )
        )

    def item_stage(
        self,
        task_id: str,
        item_index: int,
        stage_key: str,
        stage_label: str,
        *,
        message: Optional[str] = None,
    ) -> None:
        self._emit(
            ProgressEvent(
                task_id=task_id,
                kind="item_stage",
                task_name="",
                item_index=item_index,
                item_key=stage_key,
                item_label=stage_label,
                message=message,
                total=self._totals.get(task_id),
                completed=self._completed.get(task_id),
            )
        )

    def item_finish(
        self,
        task_id: str,
        item_index: int,
        success: bool = True,
        message: Optional[str] = None,
    ) -> None:
        self._emit(
            ProgressEvent(
                task_id=task_id,
                kind="item_finish",
                task_name="",
                item_index=item_index,
                success=success,
                message=message,
                total=self._totals.get(task_id),
                completed=self._completed.get(task_id),
            )
        )

    # emit helper
    def _emit(self, event: ProgressEvent) -> None:
        # publish to event bus
        try:
            self._logger.info(
                "Publishing progress event",
                kind=event.kind,
                task_id=event.task_id,
                completed=event.completed,
                total=event.total,
            )
            payload = build_progress_payload(event)
            self._publisher.publish(f"progress.{event.kind}", payload)
        except Exception:
            # エラーハンドリング内でloggerを使うと循環参照や無限ループの可能性があるため
            # ログ出力はスキップ（publish失敗は致命的ではない）
            pass

        # notify listeners (sync/async safe)
        for listener in list(self._listeners):
            try:
                result = listener(event)
                if inspect.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception:
                # エラーハンドリング内でloggerを使うと循環参照や無限ループの可能性があるため
                # ログ出力はスキップ（listener失敗は致命的ではない）
                pass


def build_progress_payload(event: ProgressEvent) -> dict[str, object]:
    """進捗イベントをシリアライズ可能なpayloadに変換する。"""
    return {
        "kind": event.kind,
        "task_id": event.task_id,
        "task_name": event.task_name,
        "total": event.total,
        "completed": event.completed,
        "stage_key": event.stage_key,
        "stage_label": event.stage_label,
        "stage_index": event.stage_index,
        "stage_count": event.stage_count,
        "success": event.success,
        "message": event.message,
        # structured
        "items": event.items,
        "item_index": event.item_index,
        "item_key": event.item_key,
        "item_label": event.item_label,
    }


class ProgressEventStore:
    """進捗イベントを保持して再送できるようにするインメモリストア。"""

    def __init__(self, max_events: int = 500) -> None:
        self._max_events = max_events
        self._events: list[dict[str, object]] = []
        self._active_tasks: set[str] = set()
        self._lock = threading.Lock()

    def record(self, event: ProgressEvent) -> None:
        """進捗イベントを保存する。"""
        payload = build_progress_payload(event)
        self.record_payload(payload)

    def record_payload(self, payload: Mapping[str, object]) -> None:
        """payload形式の進捗イベントを保存する。"""
        kind = str(payload.get("kind") or "")
        task_id = str(payload.get("task_id") or "")
        with self._lock:
            if kind == "start":
                if not self._active_tasks:
                    self._events.clear()
                if task_id:
                    self._active_tasks.add(task_id)
            elif kind == "finish":
                if task_id:
                    self._active_tasks.discard(task_id)
            self._events.append(dict(payload))
            if len(self._events) > self._max_events:
                overflow = len(self._events) - self._max_events
                if overflow > 0:
                    del self._events[:overflow]

    def snapshot(self) -> list[dict[str, object]]:
        """現在の進捗イベント履歴を返す。"""
        with self._lock:
            return list(self._events)

    def read_since(self, cursor: int) -> tuple[list[dict[str, object]], int]:
        """指定位置からの進捗イベントを返す。

        Args:
            cursor: 前回取得した位置

        Returns:
            (新規イベント一覧, 次回のcursor)
        """
        with self._lock:
            total = len(self._events)
            if cursor < 0 or cursor > total:
                cursor = 0
            return list(self._events[cursor:]), total

    async def start_listening(self, event_bus: EventBusPort) -> None:
        """イベントバスから進捗イベントを購読して保存する。"""
        sub = event_bus.subscribe(
            event_types={
                "progress.start",
                "progress.total",
                "progress.stage",
                "progress.advance",
                "progress.finish",
                "progress.items",
                "progress.item_stage",
                "progress.item_finish",
            }
        )
        try:
            while True:
                events = sub.poll(max_items=20)
                for ev in events:
                    payload = getattr(ev, "payload", None)
                    if isinstance(payload, dict):
                        self.record_payload(payload)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            sub.close()
            raise


__all__ = [
    "ProgressReporter",
    "ProgressEvent",
    "ProgressListener",
    "ProgressEventStore",
    "build_progress_payload",
]
