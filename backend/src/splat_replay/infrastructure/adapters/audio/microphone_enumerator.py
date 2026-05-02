"""マイクデバイス列挙のアダプタ。"""

from __future__ import annotations

import sys
import threading
from typing import Any, List, Optional, Protocol, cast

from splat_replay.application.interfaces.audio import MicrophoneEnumeratorPort
from structlog.stdlib import BoundLogger


class MicrophoneEnumerator(MicrophoneEnumeratorPort):
    """speech_recognition を使ってマイク一覧を取得する。"""

    def __init__(self, logger: BoundLogger) -> None:
        self._logger = logger
        self._cache_lock = threading.Lock()
        self._cached_devices: List[str] | None = None

    def invalidate_cache(self) -> None:
        """キャッシュを無効化する。次回呼び出し時に再取得される。"""
        with self._cache_lock:
            self._cached_devices = None

    def list_microphones(self) -> List[str]:
        """マイクデバイス一覧を取得する。"""
        with self._cache_lock:
            if self._cached_devices is not None:
                return list(self._cached_devices)

        try:
            if sys.platform == "win32":
                devices = self._list_windows_microphones()
                if devices:
                    self._logger.info(
                        "Windows のマイク一覧を取得しました",
                        count=len(devices),
                    )
                    self._update_cache(devices)
                    return devices
            import speech_recognition as sr

            devices = sr.Microphone.list_microphone_names()
            self._logger.info("マイク一覧を取得しました", count=len(devices))
            result = list(devices)
            self._update_cache(result)
            return result
        except Exception as exc:  # noqa: BLE001
            self._logger.error(
                "マイク一覧の取得に失敗しました", error=str(exc)
            )
            return []

    def _update_cache(self, devices: List[str]) -> None:
        with self._cache_lock:
            self._cached_devices = devices

    def _list_windows_microphones(self) -> List[str]:
        """Windows で入力デバイスだけを列挙する。"""
        try:
            import pyaudio
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "PyAudio の読み込みに失敗しました", error=str(exc)
            )
            return []

        audio = cast(_PyAudioLike, pyaudio.PyAudio())
        try:
            preferred_host_apis = self._find_preferred_host_apis(audio)
            devices: List[str] = []
            for index in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(index)
                if info.get("maxInputChannels", 0) <= 0:
                    continue
                if (
                    preferred_host_apis
                    and info.get("hostApi") not in preferred_host_apis
                ):
                    continue
                raw_name = str(info.get("name", "")).strip()
                if not raw_name:
                    continue
                if not self._should_include_device(raw_name):
                    continue
                name = self._normalize_device_name(raw_name)
                if not self._should_include_device(name):
                    continue
                devices.append(name)
            return self._unique_preserve_order(devices)
        finally:
            audio.terminate()

    def find_microphone_index(self, device_name: str) -> Optional[int]:
        """表示名からデバイスインデックスを検索する。

        list_microphones が返した名前と同じ方式（WASAPI 優先）で
        PyAudio のデバイスインデックスを返す。
        """
        if not device_name.strip():
            return None

        if sys.platform == "win32":
            result = self._find_windows_microphone_index(device_name)
            if result is not None:
                return result

        # フォールバック: sr.Microphone.list_microphone_names()
        try:
            import speech_recognition as sr

            for index, name in enumerate(
                sr.Microphone.list_microphone_names()
            ):
                if device_name.lower() in name.lower():
                    return index
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "フォールバックのマイク検索に失敗しました", error=str(exc)
            )
        return None

    def _find_windows_microphone_index(
        self, device_name: str
    ) -> Optional[int]:
        """正規化名でマッチし、MME のデバイスインデックスを返す。

        一覧表示は WASAPI で行うが、sr.Microphone はデフォルトの
        MME ホストAPI を使うため、MME 側のインデックスを返す必要がある。
        WASAPI の正規化名で照合し、対応する MME デバイスを探す。
        """
        try:
            import pyaudio
        except Exception:  # noqa: BLE001
            return None

        audio = cast(_PyAudioLike, pyaudio.PyAudio())
        try:
            # まず WASAPI の正規化名でマッチするデバイスの raw_name を取得する
            preferred_host_apis = self._find_preferred_host_apis(audio)
            matched_raw_name: Optional[str] = None
            for index in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(index)
                if info.get("maxInputChannels", 0) <= 0:
                    continue
                if (
                    preferred_host_apis
                    and info.get("hostApi") not in preferred_host_apis
                ):
                    continue
                raw_name = str(info.get("name", "")).strip()
                if not raw_name:
                    continue
                name = self._normalize_device_name(raw_name)
                if device_name.lower() in name.lower():
                    matched_raw_name = raw_name
                    break

            if matched_raw_name is None:
                return None

            # MME (hostApi=0) から同名デバイスのインデックスを返す
            for index in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(index)
                if info.get("hostApi") != 0:
                    continue
                if info.get("maxInputChannels", 0) <= 0:
                    continue
                mme_name = str(info.get("name", "")).strip()
                # MME では名前が切り詰められるため、部分一致で照合する
                if mme_name and mme_name.lower() in matched_raw_name.lower():
                    return index
            return None
        finally:
            audio.terminate()

    def _find_preferred_host_apis(self, audio: "_PyAudioLike") -> List[int]:
        """Windows の既定に近いホストAPIを優先する。"""
        preferred: List[int] = []
        for index in range(audio.get_host_api_count()):
            info = audio.get_host_api_info_by_index(index)
            name = str(info.get("name", ""))
            if "WASAPI" in name:
                preferred.append(info["index"])
        return preferred

    def _normalize_device_name(self, name: str) -> str:
        """デバイス名を正規化する。"""
        repaired = self._repair_mojibake(name)
        extracted = self._extract_parenthetical_name(repaired)
        return extracted.strip()

    def _extract_parenthetical_name(self, name: str) -> str:
        """最も外側の括弧内の名称があればそれを優先する。"""
        open_index = name.find("(")
        if open_index == -1:
            return name
        close_index = name.rfind(")")
        if close_index == -1 or close_index <= open_index:
            return name
        candidate = name[open_index + 1 : close_index].strip()
        return candidate if candidate else name

    def _repair_mojibake(self, name: str) -> str:
        """よくある文字化けを復元する。TODO: 確認（他の環境で副作用がないか）"""
        if not self._looks_like_mojibake(name):
            return name
        try:
            repaired = name.encode("cp932").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return name
        return repaired if repaired else name

    def _looks_like_mojibake(self, name: str) -> bool:
        """文字化けっぽいパターンを簡易判定する。"""
        suspicious = ("繝", "縺", "繧", "繙", "縲")
        return any(token in name for token in suspicious)

    def _should_include_device(self, name: str) -> bool:
        """入力デバイスとして表示するか判定する。"""
        if "()" in name:
            return False

        lowered = name.lower()
        blocked_tokens = (
            "sound mapper",
            "primary sound",
            "speaker",
            "speakers",
            "headphones",
            "output",
            "stereo mix",
        )
        for token in blocked_tokens:
            if token in lowered:
                return False

        blocked_jp = (
            "サウンド マッパー",
            "プライマリ サウンド",
            "スピーカー",
            "ヘッドホン",
            "ステレオ ミキサー",
        )
        for token in blocked_jp:
            if token in name:
                return False

        return True

    def _unique_preserve_order(self, devices: List[str]) -> List[str]:
        """順序を維持したまま重複を除去する。"""
        seen = set()
        unique: List[str] = []
        for device in devices:
            if device in seen:
                continue
            seen.add(device)
            unique.append(device)
        return unique


class _PyAudioLike(Protocol):
    """PyAudio の必要最低限のインターフェース。"""

    def get_device_count(self) -> int: ...

    def get_device_info_by_index(self, index: int) -> dict[str, Any]: ...

    def get_host_api_count(self) -> int: ...

    def get_host_api_info_by_index(self, index: int) -> dict[str, Any]: ...

    def terminate(self) -> None: ...
