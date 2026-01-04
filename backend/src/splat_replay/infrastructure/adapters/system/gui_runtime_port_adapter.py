"""Adapter aggregating event subscribe, command dispatch, and frame source ports for GUI."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future as ThreadFuture
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Tuple,
    cast,
    overload,
)

if TYPE_CHECKING:
    from splat_replay.application.interfaces import EventSubscription

from splat_replay.application.interfaces import (
    CommandDispatcher,
    EventSubscriber,
    FrameSource,
)
from splat_replay.application.interfaces.data import FileStats
from splat_replay.domain.models import Frame, RecordingMetadata, VideoAsset
from splat_replay.infrastructure.messaging import CommandResult
from splat_replay.infrastructure.runtime import AppRuntime


class GuiRuntimePortAdapter(CommandDispatcher, EventSubscriber, FrameSource):
    def __init__(self, runtime: AppRuntime) -> None:
        self._rt = runtime

    # CommandDispatcher
    # typed overloads (static typing aid only)
    @overload
    def submit(
        self, name: Literal["recorder.get_metadata"], **payload: object
    ) -> ThreadFuture[CommandResult[Optional[RecordingMetadata]]]: ...

    @overload
    def submit(
        self, name: Literal["recorder.start"], **payload: object
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["recorder.pause"], **payload: object
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["recorder.resume"], **payload: object
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["recorder.stop"], **payload: object
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["recorder.cancel"], **payload: object
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["asset.list"], **payload: object
    ) -> ThreadFuture[CommandResult[List["VideoAsset"]]]: ...

    @overload
    def submit(
        self, name: Literal["asset.list_with_length"], **payload: object
    ) -> ThreadFuture[
        CommandResult[
            List[Tuple["VideoAsset", float | None, FileStats | None]]
        ]
    ]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_metadata"], *, video_path: Path
    ) -> ThreadFuture[CommandResult[Optional[Dict[str, str | None]]]]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_subtitle"], *, video_path: Path
    ) -> ThreadFuture[CommandResult[Optional[str]]]: ...

    @overload
    def submit(
        self,
        name: Literal["asset.save_metadata"],
        *,
        video_path: Path,
        metadata_dict: Dict[str, str],
    ) -> ThreadFuture[CommandResult[bool]]: ...

    @overload
    def submit(
        self,
        name: Literal["asset.save_subtitle"],
        *,
        video_path: Path,
        content: str,
    ) -> ThreadFuture[CommandResult[bool]]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_length"], *, video_path: Path
    ) -> ThreadFuture[CommandResult[float | None]]: ...

    @overload
    def submit(
        self, name: Literal["asset.delete"], *, video_path: Path
    ) -> ThreadFuture[CommandResult[bool]]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_recorded_dir"], **payload: object
    ) -> ThreadFuture[CommandResult["Path"]]: ...

    @overload
    def submit(
        self, name: Literal["asset.list_edited_with_length"], **payload: object
    ) -> ThreadFuture[
        CommandResult[
            List[
                Tuple[
                    "Path",
                    float | None,
                    dict[str, str] | None,
                    FileStats | None,
                    bool,
                    bool,
                ]
            ]
        ]
    ]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_file_stats"], *, path: Path
    ) -> ThreadFuture[CommandResult[FileStats | None]]: ...

    @overload
    def submit(
        self, name: Literal["asset.has_subtitle"], *, video_path: Path
    ) -> ThreadFuture[CommandResult[bool]]: ...

    @overload
    def submit(
        self, name: Literal["asset.has_thumbnail"], *, video_path: Path
    ) -> ThreadFuture[CommandResult[bool]]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_edited_dir"], **payload: object
    ) -> ThreadFuture[CommandResult["Path"]]: ...

    @overload
    def submit(
        self, name: Literal["asset.delete_edited"], *, video_path: Path
    ) -> ThreadFuture[CommandResult[bool]]: ...

    @overload
    def submit(
        self, name: str, **payload: object
    ) -> ThreadFuture[CommandResult[object]]: ...

    def submit(
        self, name: str, **payload: object
    ) -> ThreadFuture[CommandResult[object]]:
        return self._rt.command_bus.submit(name, **payload)

    async def dispatch(self, name: str, **payload: object) -> object:
        future = self.submit(name, **payload)
        result = await asyncio.wrap_future(future)
        if not result.ok:
            if result.error is not None:
                raise result.error
            raise RuntimeError(f"Command failed: {name}")
        return result.value

    # EventSubscriber
    def subscribe(
        self, event_types: Optional[Iterable[str]] = None
    ) -> EventSubscription:
        sub = self._rt.event_bus.subscribe(event_types=event_types)
        return cast(EventSubscription, sub)

    # FrameSource proxy
    def add_listener(self, cb: Callable[[Frame], None]) -> None:
        self._rt.frame_hub.add_listener(cb)

    def remove_listener(self, cb: Callable[[Frame], None]) -> None:
        self._rt.frame_hub.remove_listener(cb)

    def get_latest(self) -> Optional[Frame]:
        return self._rt.frame_hub.get_latest()


__all__ = ["GuiRuntimePortAdapter"]
