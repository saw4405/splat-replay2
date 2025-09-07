"""Adapter aggregating event subscribe, command dispatch, and frame source ports for GUI."""

from __future__ import annotations

from concurrent.futures import Future as ThreadFuture
from typing import (
    TYPE_CHECKING,
    Any,
    List,
    Literal,
    Optional,
    Tuple,
    overload,
    Callable,
)

from splat_replay.application.interfaces import (
    CommandDispatcher,
    EventSubscriber,
    FrameSource,
    EventSubscription,
)
from splat_replay.infrastructure.runtime.commands import CommandResult
from splat_replay.infrastructure.runtime.frames import FramePacket
from splat_replay.infrastructure.runtime.runtime import AppRuntime

if TYPE_CHECKING:
    from pathlib import Path

    from splat_replay.domain.models import VideoAsset


class GuiRuntimePortAdapter(CommandDispatcher, EventSubscriber, FrameSource):
    def __init__(self, runtime: AppRuntime) -> None:
        self._rt = runtime

    # CommandDispatcher
    # typed overloads (static typing aid only)
    @overload
    def submit(
        self, name: Literal["recorder.start"], **payload: Any
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["recorder.pause"], **payload: Any
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["recorder.resume"], **payload: Any
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["recorder.stop"], **payload: Any
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["recorder.cancel"], **payload: Any
    ) -> ThreadFuture[CommandResult[None]]: ...

    @overload
    def submit(
        self, name: Literal["asset.list"], **payload: Any
    ) -> ThreadFuture[CommandResult[List["VideoAsset"]]]: ...

    @overload
    def submit(
        self, name: Literal["asset.list_with_length"], **payload: Any
    ) -> ThreadFuture[
        CommandResult[List[Tuple["VideoAsset", float | None]]]
    ]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_metadata"], *, video_path: Path
    ) -> ThreadFuture[CommandResult[Optional[dict]]]: ...

    @overload
    def submit(
        self,
        name: Literal["asset.save_metadata"],
        *,
        video_path: Path,
        metadata_dict: dict,
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
        self, name: Literal["asset.get_recorded_dir"], **payload: Any
    ) -> ThreadFuture[CommandResult["Path"]]: ...

    @overload
    def submit(
        self, name: Literal["asset.list_edited_with_length"], **payload: Any
    ) -> ThreadFuture[
        CommandResult[List[Tuple["Path", float | None, dict[str, str] | None]]]
    ]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_edited_dir"], **payload: Any
    ) -> ThreadFuture[CommandResult["Path"]]: ...

    @overload
    def submit(
        self, name: Literal["asset.delete_edited"], *, video_path: Path
    ) -> ThreadFuture[CommandResult[bool]]: ...

    @overload
    def submit(
        self, name: str, **payload: Any
    ) -> ThreadFuture[CommandResult[Any]]: ...

    def submit(
        self, name: str, **payload: Any
    ) -> ThreadFuture[CommandResult[Any]]:
        return self._rt.command_bus.submit(name, **payload)

    # EventSubscriber
    def subscribe(self, event_types=None) -> EventSubscription:
        return self._rt.event_bus.subscribe(event_types=event_types)

    # FrameSource proxy
    def add_listener(self, cb: Callable[[FramePacket], None]) -> None:
        self._rt.frame_hub.add_listener(cb)

    def remove_listener(self, cb: Callable[[FramePacket], None]) -> None:
        self._rt.frame_hub.remove_listener(cb)

    def get_latest(self) -> Optional[FramePacket]:
        return self._rt.frame_hub.get_latest()


__all__ = ["GuiRuntimePortAdapter"]
