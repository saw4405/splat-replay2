"""OBS Studio controller adapter."""

from __future__ import annotations

import asyncio
import re
from contextlib import suppress
from pathlib import Path
from types import ModuleType
from typing import Awaitable, Callable, Dict, List, Optional

import psutil
from obswsc.client import ObsWsClient
from obswsc.data import Event, Request, Response1, Response2
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    RecorderStatus,
    VideoRecorderPort,
)
from splat_replay.shared.config import OBSSettings

win32api: ModuleType | None = None
win32con: ModuleType | None = None
win32gui: ModuleType | None = None
win32process: ModuleType | None = None

try:  # Windows 以外では win32gui が存在しないため optional import
    import win32api as _win32api
    import win32con as _win32con
    import win32gui as _win32gui
    import win32process as _win32process

    win32api = _win32api
    win32con = _win32con
    win32gui = _win32gui
    win32process = _win32process
except Exception:
    # keep None for non-Windows
    pass

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
        self._logger = logger
        self._monitor_task: asyncio.Task[None] | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._status_listeners: list[StatusListener] = []
        self._initialize_settings(settings)

    def _initialize_settings(self, settings: OBSSettings) -> None:
        """設定を初期化または更新する。

        Args:
            settings: 設定
        """
        self.obs_path = settings.executable_path
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

    def update_settings(self, settings: OBSSettings) -> None:
        """設定を更新する。

        Args:
            settings: 新しい設定
        """
        self._initialize_settings(settings)
        self._logger.info("OBS settings updated")

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
                                pass
                            if re.search(
                                r"\bOBS\b(?:\s+\d+(?:\.\d+){1,2})",
                                title,
                                re.IGNORECASE,
                            ):
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
            # Windows環境では優先度「高」でプロセスを起動
            creation_flags = 0
            if win32process is not None:
                # HIGH_PRIORITY_CLASS = 0x00000080
                creation_flags = 0x00000080
                self._logger.info("OBS を優先度「高」で起動します")

            self._process = await asyncio.create_subprocess_exec(
                self.obs_path,
                cwd=self.obs_path.parent,
                creationflags=creation_flags,
            )
        except Exception as exc:  # pragma: no cover - process launch failure
            self._logger.error("OBS 起動失敗", error=str(exc))
            raise RuntimeError("OBS 起動に失敗しました") from exc

        # プロセス立ち上げを待機
        while not await self.is_running():
            await asyncio.sleep(1)

    def find_window_by_pid(self, pid: int) -> List[int]:
        if win32gui is None or win32process is None:
            self._logger.warning("win32gui が利用できません")
            return []

        result = []

        def callback(hwnd: int, _param: object) -> bool:
            if win32gui is None or win32process is None:
                return False
            if win32gui.IsWindowVisible(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    result.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)
        return result

    async def teardown(self) -> None:
        self._logger.info("OBS 終了要求")

        if self._monitor_task is not None:
            self._logger.info("OBS 接続モニタリングタスク停止")
            self._monitor_task.cancel()
            with suppress(Exception):
                await self._monitor_task
            self._monitor_task = None

        if self._is_connected:
            self._logger.info("OBS 切断")
            active, _ = await self._get_record_status()
            if active:
                self._logger.info("OBS 録画停止")
                await self.stop()
            if await self.is_virtual_camera_active():
                self._logger.info("OBS 仮想カメラ停止")
                await self.stop_virtual_camera()

        if await self.is_running() and self._process is not None:
            self._logger.info("OBS 終了処理開始")
            try:
                if win32api is not None and win32con is not None:
                    hwnds = self.find_window_by_pid(self._process.pid)
                    self._logger.info("OBS ウィンドウを閉じる")
                    for hwnd in hwnds:
                        win32api.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)

                # 最大10秒待機して終了しなければ強制終了
                try:
                    self._logger.info("OBS 終了処理待機")
                    await asyncio.wait_for(self._process.wait(), timeout=10.0)
                    self._logger.info("OBS 終了処理完了")
                except asyncio.TimeoutError:
                    self._logger.warning("OBS 強制終了")
                    self._process.terminate()
                    await self._process.wait()

            except Exception as exc:
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
        if response.res_data is None:
            return False
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
        if response.res_data is None:
            return False, False
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
        if response.res_data is None:
            self._logger.warning("録画停止レスポンスが空です")
            return None
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
