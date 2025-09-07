"""OBS 操作アダプタ。"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple, Union, cast

import psutil
from obswsc.client import ObsWsClient
from obswsc.data import Event, Request, Response1, Response2
from structlog.stdlib import BoundLogger

try:  # Windows 以外では win32gui がないため安全に import
    import win32gui
except Exception:
    win32gui = None

from splat_replay.application.interfaces import (
    RecorderStatus,
    VideoRecorderPort,
)
from splat_replay.shared.config import OBSSettings

Response = Union[Response1, Response2]


class OBSController(VideoRecorderPort):
    """OBS Studio と連携するアダプタ。"""

    def __init__(self, settings: OBSSettings, logger: BoundLogger) -> None:
        """設定を受け取って初期化する。"""

        self.obs_path = settings.executable_path
        self._logger = logger

        url = f"ws://{settings.websocket_host}:{settings.websocket_port}"
        self._client = ObsWsClient(
            url=url, password=settings.websocket_password.get_secret_value()
        )

        # obswsc の registry は asyncio.iscoroutinefunction で判定するため
        # 素直に async 関数を登録する。
        async def _event_callback(ev: Event) -> None:
            try:
                await self.event_listener(ev)
            except Exception as e:
                self._logger.warning("event listener error", error=str(e))

        # obswsc の型ヒントが "Awaitable" を受け取る形になっており、
        # 実際の実装 (コールバックを関数として登録) と食い違うため Pylance が
        # "Awaitable" ではないとの警告を出す。ライブラリ側の型問題なので
        # 明示的に無視する。
        self._client.reg_event_cb(_event_callback, "RecordStateChanged")  # type: ignore[arg-type]
        self._is_connected = False
        self._monitor_task: Optional[asyncio.Task[None]] = None
        self._process: Optional[asyncio.subprocess.Process] = None
        self._status_listeners: List[
            Callable[[RecorderStatus], Awaitable[None]]
        ] = []

    async def is_running(self) -> bool:
        """OBS が起動しているかどうかを返す。"""

        file_name = self.obs_path.name.lower()

        async def exists_process_async() -> bool:
            def _impl() -> bool:
                for proc in psutil.process_iter(["name"]):
                    try:
                        name = (proc.info.get("name") or "").lower()
                        if name == file_name:
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
                if win32gui is None:
                    return False

                handles: list[int] = []

                def enum_window(hwnd, _):
                    if win32gui is None:
                        return False
                    try:
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            if "OBS" in title:
                                handles.append(hwnd)
                    except Exception:
                        pass  # 見えない/権限系は無視

                try:
                    win32gui.EnumWindows(enum_window, None)
                except Exception:
                    return False
                return bool(handles)

            return await asyncio.to_thread(_impl)

        proc_ok, win_ok = await asyncio.gather(
            exists_process_async(),
            exists_window_async(),
        )
        return proc_ok and win_ok

    async def launch(self) -> None:
        """OBS を起動する。"""

        self._logger.info("OBS 起動指示")
        if await self.is_running():
            return

        try:
            self._process = await asyncio.create_subprocess_exec(
                self.obs_path,
                cwd=self.obs_path.parent,
            )
        except Exception as e:
            self._logger.error("OBS 起動失敗", error=str(e))
            raise RuntimeError("OBS 起動に失敗しました") from e

        # 起動直後はWebSocket接続に失敗するので起動待ちする
        while not await self.is_running():
            await asyncio.sleep(1)

    async def teardown(self) -> None:
        """OBS を終了する。"""

        self._logger.info("OBS 終了指示")

        # 受信ループ監視タスクがあれば停止
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            with suppress(Exception):
                await self._monitor_task
            self._monitor_task = None
        if self._is_connected:
            active, _ = await self._get_record_status()
            if active:
                await self.stop()
            if await self.is_virtual_camera_active():
                await self.stop_virtual_camera()

        if await self.is_running():
            try:
                if self._process is not None:
                    self._process.terminate()
                    await self._process.wait()
                    self._process = None
            except Exception as e:
                self._logger.error("OBS 終了失敗", error=str(e))

    async def connect(self):
        """OBS WebSocket に接続する。"""

        if not await self.is_running():
            self._logger.error("OBS が起動していません")
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
            except Exception as e:
                self._logger.warning("OBS へ接続できません", error=str(e))
                await asyncio.sleep(1)

        self._logger.error("OBS へ接続できませんでした")

    async def setup(self) -> None:
        if not await self.is_running():
            await self.launch()

        if not self._is_connected:
            await self.connect()

        await self.start_virtual_camera()

    async def _monitor_connection(self) -> None:
        """obswsc の受信ループ終了を検知し、自動再接続する。"""
        backoff: float = 1.0
        max_backoff: float = 10.0
        while True:
            task = getattr(self._client, "task", None)
            if task is None:
                await asyncio.sleep(0.5)
                continue
            try:
                await task
            except asyncio.CancelledError:
                return
            except Exception as e:
                self._logger.warning("OBS 受信ループ異常終了", error=str(e))

            # 受信ループが終了（切断）
            self._is_connected = False
            with suppress(Exception):
                await self._client.disconnect()
            self._logger.warning("OBS WebSocket 切断検知。自動再接続を試行")

            # 指数バックオフで再接続
            while True:
                try:
                    await self._client.connect()
                    self._is_connected = True
                    self._logger.info("OBS WebSocket 再接続完了")
                    backoff = 1.0
                    break
                except Exception as e:
                    self._logger.warning(
                        "OBS 再接続失敗", error=str(e), delay=f"{backoff:.1f}s"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(max_backoff, backoff * 1.5)

    async def _request(self, request: str) -> Response1:
        """OBS WebSocket へリクエスト送信 (1回再接続リトライ)。"""

        IDEMPOTENT = {"GetRecordStatus", "GetVirtualCamStatus"}

        for attempt in (0, 1):
            if not self._is_connected:
                await self.connect()
            try:
                response = cast(
                    Response, await self._client.request(Request(request))
                )
                if isinstance(response, Response2):
                    response = response.results[0]
                return response
            except Exception as e:
                self._logger.warning(
                    "OBS リクエスト失敗",
                    request=request,
                    error=str(e),
                    attempt=attempt,
                )
                # 切断扱いにして再接続 (冪等のみ)
                self._is_connected = False
                with suppress(Exception):
                    await asyncio.to_thread(self._client.disconnect)
                if attempt == 0 and request in IDEMPOTENT:
                    await asyncio.sleep(0.5)
                    continue
                raise RuntimeError(
                    f"OBS リクエストに失敗しました: {request}"
                ) from e

        raise RuntimeError(f"OBS リクエスト反復失敗: {request}")

    async def is_virtual_camera_active(self) -> bool:
        """仮想カメラが有効かどうかを返す。"""

        response = await self._request("GetVirtualCamStatus")
        return response.res_data.get("outputActive", False)

    async def start_virtual_camera(self):
        """OBS の仮想カメラを開始する。"""

        self._logger.info("OBS 仮想カメラ開始指示")

        if await self.is_virtual_camera_active():
            self._logger.info("仮想カメラは既に開始されています")
            return

        await self._request("StartVirtualCam")

    async def stop_virtual_camera(self):
        """OBS の仮想カメラを停止する。"""

        self._logger.info("OBS 仮想カメラ停止指示")

        if not await self.is_virtual_camera_active():
            self._logger.info("仮想カメラは既に停止されています")
            return

        await self._request("StopVirtualCam")

    async def _get_record_status(self) -> Tuple[bool, bool]:
        """録画状態を取得する。"""

        await self.connect()
        response = await self._request("GetRecordStatus")
        active = response.res_data.get("outputActive", False)
        paused = response.res_data.get("outputPaused", False)
        return active, paused

    async def start(self) -> None:
        """録画開始指示を送る。"""

        self._logger.info("OBS 録画開始指示")

        active, _ = await self._get_record_status()
        if active:
            self._logger.warning("録画は既に開始されています")
            return

        await self._request("StartRecord")

    async def stop(self) -> Optional[Path]:
        """録画停止指示を送る。"""

        self._logger.info("OBS 録画停止指示")

        active, _ = await self._get_record_status()
        if not active:
            self._logger.warning("録画が開始されていません")
            return None

        res = await self._request("StopRecord")
        output = res.res_data.get("outputPath")
        if not output:
            self._logger.warning("録画ファイル取得失敗")
            return None
        return Path(output)

    async def pause(self) -> None:
        """録画を一時停止する。"""

        self._logger.info("OBS 録画一時停止指示")

        active, paused = await self._get_record_status()
        if not active:
            self._logger.warning("録画が開始されていません")
        if paused:
            self._logger.warning("録画は既に一時停止されています")
            return

        await self._request("PauseRecord")

    async def resume(self) -> None:
        """録画を再開する。"""

        self._logger.info("OBS 録画再開指示")

        _, paused = await self._get_record_status()
        if not paused:
            self._logger.warning("録画が一時停止されていません")
            return

        await self._request("ResumeRecord")

    def add_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None:
        """録画状態変化リスナーを登録する。"""
        self._status_listeners.append(listener)

    def remove_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None:
        """録画状態変化リスナーを解除する。"""
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)

    async def event_listener(self, event: Event):
        if event.event_type != "RecordStateChanged":
            return

        state = event.event_data["outputState"]
        if state == "OBS_WEBSOCKET_OUTPUT_STARTED":
            status = "started"
        elif state == "OBS_WEBSOCKET_OUTPUT_PAUSED":
            status = "paused"
        elif state == "OBS_WEBSOCKET_OUTPUT_RESUMED":
            status = "resumed"
        elif state == "OBS_WEBSOCKET_OUTPUT_STOPPED":
            status = "stopped"
        elif state == "OBS_WEBSOCKET_OUTPUT_STARTING":
            return
        elif state == "OBS_WEBSOCKET_OUTPUT_STOPPING":
            return
        else:
            self._logger.warning("不明な録画状態", state=state)
            return

        for listener in self._status_listeners:
            try:
                await listener(status)
            except Exception as e:
                self._logger.error(
                    "状態リスナーの呼び出しに失敗", error=str(e)
                )
