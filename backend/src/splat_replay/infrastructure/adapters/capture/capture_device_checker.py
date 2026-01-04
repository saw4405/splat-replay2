"""キャプチャデバイス接続確認アダプタ。"""

from __future__ import annotations

import subprocess
import sys

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CaptureDeviceSettingsView,
)


def _get_video_devices_from_ffmpeg(
    logger: BoundLogger, timeout: float = 10
) -> list[str]:
    """FFmpegを使用してビデオデバイス一覧を取得する内部関数。

    Args:
        logger: ロガー
        timeout: タイムアウト秒数

    Returns:
        ビデオデバイス名のリスト
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-list_devices",
                "true",
                "-f",
                "dshow",
                "-i",
                "dummy",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # デコードエラーを無視して?に置換
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
            if sys.platform == "win32"
            else 0,
        )

        # ビデオデバイスのみを抽出
        # Format: [dshow @ ...] "Device Name" (video)
        devices: list[str] = []
        lines = result.stderr.split("\n")

        for line in lines:
            if "(video)" in line and '"' in line:
                start = line.find('"')
                end = line.rfind('"')
                if start != -1 and end != -1 and start < end:
                    device_name = line[start + 1 : end]
                    if device_name and device_name not in devices:
                        devices.append(device_name)

        return devices

    except FileNotFoundError:
        logger.error(
            "FFmpeg not found. Please install FFmpeg to list video devices."
        )
        return []
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg device enumeration timed out")
        return []
    except Exception as e:
        logger.error("Failed to enumerate video devices", error=str(e))
        return []


class CaptureDeviceChecker(CaptureDevicePort):
    """キャプチャデバイスの接続状態を確認する。"""

    def __init__(
        self,
        settings: CaptureDeviceSettingsView,
        logger: BoundLogger,
    ) -> None:
        """設定を受け取り初期化する。"""

        self.device_name = settings.name
        self.logger = logger

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None:
        """設定を更新する。

        Args:
            settings: 新しい設定
        """
        self.device_name = settings.name
        self.logger.info(
            "Capture device settings updated", device_name=settings.name
        )

    def is_connected(self) -> bool:
        """デバイスが接続済みかを返す。

        FFmpegのDirectShowを使用してビデオデバイスを列挙し、
        設定されたデバイス名が存在するかを確認します。
        """
        # Windows 以外では実機での確認ができないため常に接続済みとみなす
        if sys.platform != "win32":
            self.logger.warning("Check skipped (not Windows)")
            return True

        devices = _get_video_devices_from_ffmpeg(self.logger)
        return self.device_name in devices


class CaptureDeviceEnumerator(CaptureDeviceEnumeratorPort):
    """キャプチャデバイスの列挙を行う。"""

    def __init__(self, logger: BoundLogger) -> None:
        """初期化する。"""
        self.logger = logger

    def list_video_devices(self) -> list[str]:
        """ビデオキャプチャデバイス一覧を取得する。

        OBSと同じく、FFmpegのDirectShowを使用してビデオデバイスのみを列挙します。
        オーディオデバイスは含まれません。
        """
        # Windows 以外では空リストを返す
        if sys.platform != "win32":
            self.logger.warning("Device enumeration skipped (not Windows)")
            return []

        devices = _get_video_devices_from_ffmpeg(self.logger)
        self.logger.info("Video devices enumerated", count=len(devices))
        return devices
