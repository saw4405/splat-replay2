"""Progress event bus and reporter.

AutoEditor / AutoUploader publish progress to GUI via EventPublisher.
Threading model: events are dispatched to listeners; GUI controller bridges to Tk.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import List, Optional, Protocol

from structlog.stdlib import get_logger

from splat_replay.application.interfaces import EventPublisher

logger = get_logger()


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
    def __call__(self, event: ProgressEvent) -> None: ...


class ProgressReporter:
    """Progress publisher with simple and structured APIs."""

    def __init__(self, publisher: EventPublisher) -> None:
        self._listeners: List[ProgressListener] = []
        self._totals: dict[str, Optional[int]] = {}
        self._completed: dict[str, int] = {}
        self._publisher = publisher

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
            self._publisher.publish(
                f"progress.{event.kind}",
                {
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
                },
            )
        except Exception:
            pass

        # notify listeners (sync/async safe)
        for listener in list(self._listeners):
            try:
                if inspect.iscoroutinefunction(listener):
                    asyncio.create_task(listener(event))
                else:
                    listener(event)
            except Exception as e:
                logger.exception("Progress listener error", error=e)


__all__ = [
    "ProgressReporter",
    "ProgressEvent",
    "ProgressListener",
]
