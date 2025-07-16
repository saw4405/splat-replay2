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
        self._process: subprocess.Popen[bytes] | None = None

    def is_running(self) -> bool:
        """OBS が起動しているかどうかを返す。"""

        def exists_process(file_name: str) -> bool:
            for proc in psutil.process_iter(["name"]):
                if proc.info["name"] == file_name:
                    return True
            return False

        def exists_window(title: str) -> bool:
            if win32gui is None:  # pragma: no cover - OS 依存
                logger.warning("win32gui が利用できません")
                return False

            def enum_window(hwnd, result):
                if win32gui is None:  # pragma: no cover - OS 依存
                    logger.warning("win32gui が利用できません")
                    return False
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if title in window_title:
                        result.append(hwnd)

            windows = []
            win32gui.EnumWindows(enum_window, windows)
            return bool(windows)

        return exists_process(
            self._settings.executable_path.name
        ) and exists_window("OBS")

    def launch(self) -> None:
        """OBS を起動する。"""

        logger.info("OBS 起動指示")
        if self.is_running():
            return

        try:
            file_name = self._settings.executable_path.name
            directory = self._settings.executable_path.parent
            self._process = subprocess.Popen(
                file_name, cwd=directory, shell=True
            )
        except Exception as e:  # pragma: no cover - 実機依存
            logger.error("OBS 起動失敗", error=str(e))
            raise RuntimeError("OBS 起動に失敗しました") from e

        # 起動直後はWebSocket接続に失敗するので起動待ちする
        while not self.is_running():
            time.sleep(1)

    def terminate(self) -> None:
        """OBS を終了する。"""

        logger.info("OBS 終了指示")

        if self.is_connected():
            active, _ = self._get_record_status()
            if active:
                self.stop()
            if self.is_virtual_camera_active():
                self.stop_virtual_camera()

        if self.is_running():
            try:
                if self._process is not None:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                    self._process = None
            except Exception as e:
                logger.error("OBS 終了失敗", error=str(e))

    def close(self) -> None:
        self.terminate()

    def is_connected(self) -> bool:
        """WebSocket が接続済みか確認する。"""

        return self._ws.ws is not None and self._ws.ws.connected

    def connect(self) -> None:
        """OBS WebSocket に接続する。"""

        logger.info("OBS WebSocket 接続試行")

        if not self.is_running():
            logger.error("OBS が起動していません")
            raise RuntimeError("OBS が起動していません")

        if self.is_connected():
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

    def start_virtual_camera(self) -> None:
        """OBS の仮想カメラを開始する。"""

        logger.info("OBS 仮想カメラ開始指示")
        if not self.is_connected():
            self.connect()
        status = self._ws.call(requests.GetVirtualCamStatus())
        if not status.datain.get("outputActive", False):
            self._ws.call(requests.StartVirtualCam())

    def stop_virtual_camera(self) -> None:
        """OBS の仮想カメラを停止する。"""

        logger.info("OBS 仮想カメラ停止指示")
        if not self.is_connected():
            self.connect()
        status = self._ws.call(requests.GetVirtualCamStatus())
        if status.datain.get("outputActive", False):
            self._ws.call(requests.StopVirtualCam())

    def is_virtual_camera_active(self) -> bool:
        """仮想カメラが有効かどうかを返す。"""

        if not self.is_connected():
            self.connect()
        status = self._ws.call(requests.GetVirtualCamStatus())
        return status.datain.get("outputActive", False)

    def _get_record_status(self) -> tuple[bool, bool]:
        """録画状態を取得する。"""

        if not self.is_connected():
            self.connect()
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
