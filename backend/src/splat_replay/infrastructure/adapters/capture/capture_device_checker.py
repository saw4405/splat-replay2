"""キャプチャデバイス接続確認アダプタ。"""

from __future__ import annotations

import re
import subprocess
import sys

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CaptureDeviceSettingsView,
)

_DEVICE_ENUMERATION_TIMEOUT_SECONDS = 10.0
_AVFOUNDATION_VIDEO_DEVICES_HEADER = "AVFoundation video devices:"
_AVFOUNDATION_AUDIO_DEVICES_HEADER = "AVFoundation audio devices:"
_VIDEO_DEVICE_LINE = re.compile(r"\[(\d+)\]\s+(.+?)\s*$")
_PERMISSION_ERROR_MARKERS = (
    "permission denied",
    "not authorized",
    "not permitted",
    "access denied",
)


def _get_video_devices_from_avfoundation(
    logger: BoundLogger,
    timeout: float = _DEVICE_ENUMERATION_TIMEOUT_SECONDS,
) -> list[str]:
    """macOS の FFmpeg AVFoundation 出力から映像デバイス名を得る。"""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-f",
                "avfoundation",
                "-list_devices",
                "true",
                "-i",
                "",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError:
        logger.error("FFmpeg が見つからず映像デバイスを列挙できません")
        return []
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg AVFoundation の列挙がタイムアウトしました")
        return []
    except Exception as exc:  # noqa: BLE001
        logger.error("AVFoundation の列挙に失敗しました", error=str(exc))
        return []

    output = result.stderr
    lowered_output = output.lower()
    if any(marker in lowered_output for marker in _PERMISSION_ERROR_MARKERS):
        logger.warning("AVFoundation 映像デバイスへのアクセスが拒否されました")
        return []

    lines = output.splitlines()
    video_header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if _AVFOUNDATION_VIDEO_DEVICES_HEADER in line
        ),
        None,
    )
    if video_header_index is None:
        logger.warning(
            "FFmpeg から AVFoundation の映像一覧を取得できませんでした",
            return_code=result.returncode,
        )
        return []

    audio_header_index = next(
        (
            index
            for index in range(video_header_index + 1, len(lines))
            if _AVFOUNDATION_AUDIO_DEVICES_HEADER in lines[index]
        ),
        None,
    )
    if audio_header_index is None:
        logger.warning("FFmpeg の AVFoundation デバイス一覧が不完全です")
        return []

    devices: list[str] = []
    for line in lines[video_header_index + 1 : audio_header_index]:
        match = _VIDEO_DEVICE_LINE.search(line)
        if match is None:
            continue
        name = match.group(2).strip()
        # AVFoundation は画面も映像ソースとして出すため、実機がなくても
        # 準備完了になることを避けるため画面項目を除外する。
        if not name or re.fullmatch(r"Capture screen \d+", name):
            continue
        if name not in devices:
            devices.append(name)

    return devices


def _get_video_devices_from_ffmpeg(
    logger: BoundLogger,
    timeout: float = _DEVICE_ENUMERATION_TIMEOUT_SECONDS,
) -> list[str]:
    """FFmpegを使用してビデオデバイス一覧を取得する内部関数。

    Args:
        logger: ロガー
        timeout: タイムアウト秒数

    Returns:
        ビデオデバイス名のリスト
    """
    if sys.platform == "darwin":
        return _get_video_devices_from_avfoundation(logger, timeout)
    if sys.platform != "win32":
        return []

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
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
        """現在の映像デバイス一覧に選択名があるかを返す。"""
        if sys.platform == "darwin":
            if not self.device_name.strip():
                return False
            devices = _get_video_devices_from_ffmpeg(self.logger)
            return self.device_name in devices

        # Windows 以外では従来どおり実機での確認を省略する
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
        """FFmpeg から映像キャプチャデバイスのみを取得する。"""
        if sys.platform not in {"win32", "darwin"}:
            self.logger.warning("Device enumeration skipped (unsupported OS)")
            return []

        devices = _get_video_devices_from_ffmpeg(self.logger)
        self.logger.info("Video devices enumerated", count=len(devices))
        return devices
