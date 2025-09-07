"""Infrastructure command bus (moved).

GUI などメインスレッド (非 asyncio) からも安全に非同期コマンドを
投げられるように、`asyncio.get_running_loop()` 依存を排除し、
バックグラウンドで動作する runtime の event loop に対して
`run_coroutine_threadsafe` で投入する方式に変更した。

従来は GUI スレッドで `submit` を呼ぶと `RuntimeError: no running event loop`
が発生していた。
"""

from __future__ import annotations

import asyncio
from concurrent.futures import Future as ThreadFuture
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Optional,
    TypeVar,
    overload,
    Literal,
    List,
    Tuple,
)

if TYPE_CHECKING:  # type-only imports to avoid runtime coupling
    from pathlib import Path
    from splat_replay.domain.models import VideoAsset

T = TypeVar("T")


@dataclass(slots=True)
class CommandResult(Generic[T]):
    ok: bool
    value: Optional[T] = None
    error: Optional[Exception] = None


class CommandBus:
    """コマンドを非同期実行するバス。

    GUI など非イベントループスレッドから呼ばれても動作するよう、
    runtime の event loop 参照を保持し `run_coroutine_threadsafe` で
    タスクを投入する。戻り値は `concurrent.futures.Future` 互換の
    オブジェクト (型ヒント上は ThreadFuture) なので、既存の
    `add_done_callback` 利用コードはそのまま動く。
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def register(
        self, name: str, handler: Callable[..., Awaitable[Any]]
    ) -> None:
        self._handlers[name] = handler

    # ---- typed overloads (for static checkers) ----
    # recorder controls (no payload, no return)
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

    # asset queries
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
        self, name: Literal["asset.get_metadata"], *, video_path: "Path"
    ) -> ThreadFuture[CommandResult[Optional[dict]]]: ...

    @overload
    def submit(
        self,
        name: Literal["asset.save_metadata"],
        *,
        video_path: "Path",
        metadata_dict: dict,
    ) -> ThreadFuture[CommandResult[bool]]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_length"], *, video_path: "Path"
    ) -> ThreadFuture[CommandResult[float | None]]: ...

    @overload
    def submit(
        self, name: Literal["asset.delete"], *, video_path: "Path"
    ) -> ThreadFuture[CommandResult[bool]]: ...

    @overload
    def submit(
        self, name: Literal["asset.get_recorded_dir"], **payload: Any
    ) -> ThreadFuture[CommandResult["Path"]]: ...

    # edited assets
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
        self, name: Literal["asset.delete_edited"], *, video_path: "Path"
    ) -> ThreadFuture[CommandResult[bool]]: ...

    # permissive dynamic overload for non-literal names
    @overload
    def submit(
        self, name: str, **payload: Any
    ) -> ThreadFuture[CommandResult[Any]]: ...

    # fallback (dynamic)
    def submit(
        self, name: str, **payload: Any
    ) -> ThreadFuture[CommandResult[Any]]:
        if self._loop is None or not self._loop.is_running():
            tf: ThreadFuture[CommandResult[Any]] = ThreadFuture()
            tf.set_result(
                CommandResult(False, error=RuntimeError("loop not running"))
            )
            return tf

        handler = self._handlers.get(name)
        if handler is None:
            tf: ThreadFuture[CommandResult[Any]] = ThreadFuture()
            tf.set_result(CommandResult(False, error=KeyError(name)))
            return tf

        async def run() -> CommandResult[Any]:
            try:
                val = await handler(**payload)
                return CommandResult(True, value=val)
            except Exception as e:  # noqa: BLE001
                return CommandResult(False, error=e)

        # ループスレッドに安全に投入
        return asyncio.run_coroutine_threadsafe(run(), self._loop)


__all__ = ["CommandBus", "CommandResult"]
