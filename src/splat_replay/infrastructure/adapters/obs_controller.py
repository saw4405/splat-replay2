"""OBS Studio controller adapter."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Awaitable, Callable, Dict, Optional

import psutil
from obswsc.client import ObsWsClient
from obswsc.data import Event, Request, Response1, Response2
from structlog.stdlib import BoundLogger

try:  # Windows 以外では win32gui が存在しないため optional import
    import win32gui
except Exception:  # pragma: no cover - 環境依存
    win32gui = None  # type: ignore[assignment]

from splat_replay.application.interfaces import (
    RecorderStatus,
    VideoRecorderPort,
)
from splat_replay.shared.config import OBSSettings

Response = Response1 | Response2
StatusListener = Callable[[RecorderStatus], Awaitable[None]]
STATE_TO_STATUS: Dict[str, RecorderStatus] = {
    "OBS_WEBSOCKET_OUTPUT_STARTED": "started",
    "OBS_WEBSOCKET_OUTPUT_PAUSED": "paused",
    "OBS_WEBSOCKET_OUTPUT_RESUMED": "resumed",
    "OBS_WEBSOCKET_OUTPUT_STOPPED": "stopped",
}


class OBSController(VideoRecorderPort):
    """Adapter that controls OBS Studio via obs-ws."""

    def __init__(self, settings: OBSSettings, logger: BoundLogger) -> None:
        self.obs_path = settings.executable_path
        self._logger = logger

        url = f"ws://{settings.websocket_host}:{settings.websocket_port}"
        self._client = ObsWsClient(
            url=url, password=settings.websocket_password.get_secret_value()
        )

        async def _event_callback(event: Event) -> None:
            try:
                await self.event_listener(event)
            except Exception as exc:  # pragma: no cover - logging path
                self._logger.warning("event listener error", error=str(exc))

        self._client.reg_event_cb(_event_callback, "RecordStateChanged")
        self._is_connected = False
        self._monitor_task: asyncio.Task[None] | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._status_listeners: list[StatusListener] = []

    async def is_running(self) -> bool:
        file_name = self.obs_path.name.lower()

        async def exists_process_async() -> bool:
            def _impl() -> bool:
                for proc in psutil.process_iter(["name"]):
                    try:
                        name_obj = proc.info.get("name")
                        if (
                            isinstance(name_obj, str)
                            and name_obj.lower() == file_name
                        ):
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                return False

            return await asyncio.to_thread(_impl)

        async def exists_window_async() -> bool:
            if win32gui is None:
                self._logger.warning("win32gui が利用できません")
                return False

            def _impl() -> bool:
                if win32gui is None:  # pragma: no cover - defensive
                    return False

                handles: list[int] = []

                def enum_window(hwnd: int, _param: Optional[int]) -> bool:
                    if win32gui is None:  # pragma: no cover - defensive
                        return False
                    try:
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            if "OBS" in title:
                                handles.append(hwnd)
                    except Exception:  # pragma: no cover - defensive
                        return True
                    return True

                try:
                    win32gui.EnumWindows(enum_window, None)
                except Exception:  # pragma: no cover - defensive
                    return False
                return bool(handles)

            return await asyncio.to_thread(_impl)

        proc_ok, win_ok = await asyncio.gather(
            exists_process_async(), exists_window_async()
        )
        return proc_ok and win_ok

    async def launch(self) -> None:
        self._logger.info("OBS 起動要求")
        if await self.is_running():
            return

        try:
            self._process = await asyncio.create_subprocess_exec(
                self.obs_path,
                cwd=self.obs_path.parent,
            )
        except Exception as exc:  # pragma: no cover - process launch failure
            self._logger.error("OBS 起動失敗", error=str(exc))
            raise RuntimeError("OBS 起動に失敗しました") from exc

        # プロセス立ち上げを待機
        while not await self.is_running():
            await asyncio.sleep(1)

    async def teardown(self) -> None:
        self._logger.info("OBS 終了要求")

        if self._monitor_task is not None:
            self._monitor_task.cancel()
            with suppress(Exception):
                await self._monitor_task
            self._monitor_task = None

        if self._is_connected:
            active, _paused = await self._get_record_status()
            if active:
                await self.stop()
            if await self.is_virtual_camera_active():
                await self.stop_virtual_camera()

        if await self.is_running() and self._process is not None:
            try:
                self._process.terminate()
                await self._process.wait()
            except Exception as exc:  # pragma: no cover - logging path
                self._logger.error("OBS 終了失敗", error=str(exc))
            finally:
                self._process = None

    async def connect(self) -> None:
        if not await self.is_running():
            raise RuntimeError("OBS が起動していません")

        for _ in range(5):
            try:
                await self._client.connect()
                self._is_connected = True
                if self._monitor_task is None or self._monitor_task.done():
                    self._monitor_task = asyncio.create_task(
                        self._monitor_connection()
                    )
                return
            except Exception as exc:
                self._logger.warning("OBS 接続失敗", error=str(exc))
                await asyncio.sleep(1)

        self._logger.error("OBS への接続に失敗")
        raise RuntimeError("OBS への接続に失敗しました")

    async def setup(self) -> None:
        if not await self.is_running():
            await self.launch()
        if not self._is_connected:
            await self.connect()
        await self.start_virtual_camera()

    async def _monitor_connection(self) -> None:
        backoff = 1.0
        max_backoff = 10.0
        while True:
            task: Awaitable[object] | None = getattr(
                self._client, "task", None
            )
            if task is None:
                await asyncio.sleep(0.5)
                continue
            try:
                await task
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self._logger.warning("OBS 受信ループ異常終了", error=str(exc))

            self._is_connected = False
            with suppress(Exception):
                await self._client.disconnect()
            self._logger.warning("OBS WebSocket 切断。再接続します")

            while True:
                try:
                    await self._client.connect()
                    self._is_connected = True
                    self._logger.info("OBS WebSocket 再接続完了")
                    backoff = 1.0
                    break
                except Exception as exc:
                    self._logger.warning(
                        "OBS 再接続失敗",
                        error=str(exc),
                        delay=f"{backoff:.1f}s",
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(max_backoff, backoff * 1.5)

    async def _request(self, request: str) -> Response1:
        idempotent: set[str] = {"GetRecordStatus", "GetVirtualCamStatus"}

        for attempt in (0, 1):
            if not self._is_connected:
                await self.connect()
            try:
                response = await self._client.request(Request(request))
                if isinstance(response, Response2):
                    return response.results[0]
                return response
            except Exception as exc:
                self._logger.warning(
                    "OBS リクエスト失敗",
                    request=request,
                    error=str(exc),
                    attempt=attempt,
                )
                self._is_connected = False
                with suppress(Exception):
                    await self._client.disconnect()
                if attempt == 0 and request in idempotent:
                    await asyncio.sleep(0.5)
                    continue
                raise RuntimeError(
                    f"OBS リクエストに失敗しました: {request}"
                ) from exc

        raise RuntimeError(f"OBS リクエストが失敗しました: {request}")

    async def is_virtual_camera_active(self) -> bool:
        response = await self._request("GetVirtualCamStatus")
        return bool(response.res_data.get("outputActive", False))

    async def start_virtual_camera(self) -> None:
        self._logger.info("OBS 仮想カメラ開始要求")
        if await self.is_virtual_camera_active():
            self._logger.info("仮想カメラは既に開始済み")
            return
        await self._request("StartVirtualCam")

    async def stop_virtual_camera(self) -> None:
        self._logger.info("OBS 仮想カメラ停止要求")
        if not await self.is_virtual_camera_active():
            self._logger.info("仮想カメラは既に停止済み")
            return
        await self._request("StopVirtualCam")

    async def _get_record_status(self) -> tuple[bool, bool]:
        await self.connect()
        response = await self._request("GetRecordStatus")
        active = bool(response.res_data.get("outputActive", False))
        paused = bool(response.res_data.get("outputPaused", False))
        return active, paused

    async def start(self) -> None:
        self._logger.info("OBS 録画開始要求")
        active, _paused = await self._get_record_status()
        if active:
            self._logger.warning("録画は既に開始済みです")
            return
        await self._request("StartRecord")

    async def stop(self) -> Path | None:
        self._logger.info("OBS 録画停止要求")
        active, _paused = await self._get_record_status()
        if not active:
            self._logger.warning("録画は開始されていません")
            return None
        response = await self._request("StopRecord")
        output = response.res_data.get("outputPath")
        if not isinstance(output, str) or not output:
            self._logger.warning("録画ファイルの取得に失敗しました")
            return None
        return Path(output)

    async def pause(self) -> None:
        self._logger.info("OBS 録画一時停止要求")
        active, paused = await self._get_record_status()
        if not active:
            self._logger.warning("録画は開始されていません")
            return
        if paused:
            self._logger.warning("録画は既に一時停止中です")
            return
        await self._request("PauseRecord")

    async def resume(self) -> None:
        self._logger.info("OBS 録画再開要求")
        _active, paused = await self._get_record_status()
        if not paused:
            self._logger.warning("録画は一時停止されていません")
            return
        await self._request("ResumeRecord")

    def add_status_listener(self, listener: StatusListener) -> None:
        self._status_listeners.append(listener)

    def remove_status_listener(self, listener: StatusListener) -> None:
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)

    async def event_listener(self, event: Event) -> None:
        if event.event_type != "RecordStateChanged":
            return
        state_obj = event.event_data.get("outputState")
        if not isinstance(state_obj, str):
            self._logger.warning("不明な録画状態", state=state_obj)
            return
        status = STATE_TO_STATUS.get(state_obj)
        if status is None:
            return
        await self._notify_status(status)

    async def _notify_status(self, status: RecorderStatus) -> None:
        for listener in list(self._status_listeners):
            try:
                await listener(status)
            except Exception as exc:  # pragma: no cover - logging path
                self._logger.error("ステータス通知でエラー", error=str(exc))
