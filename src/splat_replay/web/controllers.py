"""Web API 用コントローラ。"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future as ThreadFuture
from pathlib import Path
from typing import Generic, TypeVar

from structlog.stdlib import BoundLogger

from splat_replay.application.services import AutoRecorder, DeviceChecker
from splat_replay.infrastructure.runtime.commands import (
    CommandBus,
    CommandResult,
)
from splat_replay.infrastructure.runtime.runtime import AppRuntime

T = TypeVar("T")


class CommandExecutionError(RuntimeError):
    """コマンド実行失敗を表すエラー。"""


class AutoRecorderAlreadyRunningError(RuntimeError):
    """自動録画が既に実行中であることを示すエラー。"""


class _CommandResultAwaiter(Generic[T]):
    """`CommandResult` を安全に待ち受けるユーティリティ。"""

    async def __call__(self, future: ThreadFuture[CommandResult[T]]) -> T:
        result = await asyncio.wrap_future(future)
        if not result.ok:
            message = str(result.error) if result.error else "原因不明のエラー"
            raise CommandExecutionError(message)
        if result.value is None:
            raise CommandExecutionError("コマンドが値を返しませんでした。")
        return result.value


class AssetController:
    """動画アセット関連の API コントローラ。"""

    def __init__(self, command_bus: CommandBus) -> None:
        self._command_bus = command_bus
        self._awaiter: _CommandResultAwaiter[Path] = _CommandResultAwaiter()

    async def get_edited_dir(self) -> str:
        """編集済み動画ディレクトリのパスを取得する。"""

        path = await self._awaiter(
            self._command_bus.submit("asset.get_edited_dir")
        )
        return str(path)


class AutoRecorderController:
    """自動録画の起動を担当するコントローラ。"""

    def __init__(
        self,
        runtime: AppRuntime,
        auto_recorder: AutoRecorder,
        device_checker: DeviceChecker,
        logger: BoundLogger,
    ) -> None:
        self._runtime = runtime
        self._auto_recorder = auto_recorder
        self._device_checker = device_checker
        self._logger = logger
        self._lock = threading.Lock()
        self._task: asyncio.Future[bool] | None = None

    def is_running(self) -> bool:
        """自動録画タスクが稼働中かどうかを返す。"""

        with self._lock:
            task = self._task
        return task is not None and not task.done()

    def start_auto_recorder(self, wait_timeout: float | None = None) -> bool:
        """自動録画をバックグラウンドで起動する。

        戻り値はキャプチャデバイス接続待機が必要かどうかを表す。
        """

        loop = self._runtime.loop
        if loop is None:
            raise RuntimeError(
                "AppRuntime のイベントループが初期化されていません。"
            )

        with self._lock:
            if self.is_running():
                raise AutoRecorderAlreadyRunningError(
                    "自動録画は既に実行中です。"
                )

            needs_wait = not self._device_checker.is_connected()

            def _launch() -> None:
                async def runner() -> bool:
                    try:
                        connected = True
                        if needs_wait:
                            connected = await self._device_checker.wait_for_device_connection(
                                timeout=wait_timeout
                            )
                            if not connected:
                                self._logger.error(
                                    "キャプチャデバイス未接続のため自動録画を開始できません"
                                )
                                return False
                        await self._auto_recorder.execute()
                        return True
                    except Exception as exc:  # noqa: BLE001
                        self._logger.error(
                            "自動録画処理でエラーが発生しました。",
                            error=str(exc),
                        )
                        return False
                    finally:
                        with self._lock:
                            self._task = None

                task = loop.create_task(runner())
                with self._lock:
                    self._task = task

            loop.call_soon_threadsafe(_launch)

        return needs_wait


__all__ = [
    "AssetController",
    "AutoRecorderAlreadyRunningError",
    "AutoRecorderController",
    "CommandExecutionError",
]
