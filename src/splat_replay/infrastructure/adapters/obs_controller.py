"""OBS 操作アダプタ。"""

from __future__ import annotations

import subprocess
from pathlib import Path
import time

import psutil
from obswebsocket import obsws, requests

try:  # Windows 以外では win32gui がないため安全に import
    import win32gui
except Exception:  # pragma: no cover - OS 依存
    win32gui = None

from splat_replay.application.interfaces import OBSControlPort
from splat_replay.shared.config import OBSSettings
from splat_replay.shared.logger import get_logger

logger = get_logger()


class OBSController(OBSControlPort):
    """OBS Studio と連携するアダプタ。"""

    def __init__(self, settings: OBSSettings) -> None:
        """設定を受け取って初期化する。"""

        self._settings = settings
        self._ws = obsws(
            settings.websocket_host,
            settings.websocket_port,
            settings.websocket_password,
            on_disconnect=self._on_disconnect,
        )
        self._process: subprocess.Popen[str] | None = None

        # インスタンス生成時に接続を試みる
        try:
            self.connect()
        except Exception as e:  # pragma: no cover - 実機依存
            logger.warning("OBS への接続に失敗しました", error=str(e))

    def connect(self) -> None:
        """OBS WebSocket に接続する。"""

        if self.is_connected():
            return

        if not self.is_running():
            try:
                self.launch()
            except Exception as e:
                logger.warning("OBS 起動失敗", error=str(e))
                return

        for _ in range(5):
            try:
                self._ws.connect()
                return
            except Exception as e:  # pragma: no cover - 実機依存
                logger.warning("OBS へ接続できません", error=str(e))
                time.sleep(1)

        logger.error("OBS へ接続できませんでした")

    def _on_disconnect(self, ws) -> None:
        """切断時に再接続を試みる。"""

        logger.warning("OBS から切断されました")
        self.connect()

    def is_connected(self) -> bool:
        """WebSocket が接続済みか確認する。"""

        return self._ws.ws is not None and self._ws.ws.connected

    def _get_record_status(self) -> tuple[bool, bool]:
        """録画状態を取得する。"""

        status = self._ws.call(requests.GetRecordStatus())
        active = status.datain.get("outputActive", False)
        paused = status.datain.get("outputPaused", False)
        return active, paused

    def start(self) -> None:
        """録画開始指示を送る。"""

        logger.info("OBS 録画開始指示")

        active, _ = self._get_record_status()
        if not active:
            self._ws.call(requests.StartRecord())

    def stop(self) -> Path:
        """録画停止指示を送る。"""

        logger.info("OBS 録画停止指示")
        active, _ = self._get_record_status()
        if not active:
            raise RuntimeError("録画は開始されていません")
        res = self._ws.call(requests.StopRecord())
        output = res.datain.get("outputPath")
        if not output:
            raise RuntimeError("録画ファイル取得失敗")
        return Path(output)

    def pause(self) -> None:
        """録画を一時停止する。"""

        logger.info("OBS 録画一時停止指示")
        active, paused = self._get_record_status()
        if active and not paused:
            self._ws.call(requests.PauseRecord())

    def resume(self) -> None:
        """録画を再開する。"""

        logger.info("OBS 録画再開指示")
        _, paused = self._get_record_status()
        if paused:
            self._ws.call(requests.ResumeRecord())

    def is_running(self) -> bool:
        """OBS が起動しているかどうかを返す。"""

        exe_name = Path(self._settings.executable_path).name

        def exists_process() -> bool:
            for proc in psutil.process_iter(["name"]):
                if proc.info.get("name") == exe_name:
                    return True
            return False

        if win32gui is None:
            return exists_process()

        def exists_window() -> bool:
            def enum_window(hwnd, result):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "OBS" in title:
                        result.append(hwnd)

            windows: list[int] = []
            win32gui.EnumWindows(enum_window, windows)
            return bool(windows)

        return exists_process() and exists_window()

    def launch(self) -> None:
        """OBS を起動する。"""

        logger.info("OBS 起動指示")
        if self.is_running():
            return

        try:
            self._process = subprocess.Popen([self._settings.executable_path])
        except Exception as e:  # pragma: no cover - 実機依存
            logger.error("OBS 起動失敗", error=str(e))
            raise RuntimeError("OBS 起動に失敗しました") from e

    def start_virtual_camera(self) -> None:
        """OBS の仮想カメラを開始する。"""

        logger.info("OBS 仮想カメラ開始指示")
        status = self._ws.call(requests.GetVirtualCamStatus())
        if not status.datain.get("outputActive", False):
            self._ws.call(requests.StartVirtualCam())
