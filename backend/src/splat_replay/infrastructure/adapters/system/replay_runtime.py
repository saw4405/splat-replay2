"""リプレイ E2E 用に外部デバイスへ到達しないアダプター。"""

from __future__ import annotations

from splat_replay.application.interfaces import (
    CaptureDeviceEnumeratorPort,
    MicrophoneEnumeratorPort,
    PowerPort,
)
from splat_replay.application.interfaces.data import CaptureDeviceDescriptor


class ReplayCaptureDeviceEnumerator(CaptureDeviceEnumeratorPort):
    """リプレイ実行では実機キャプチャデバイスを列挙しない。"""

    def list_video_devices(self) -> list[str]:
        return []

    def list_video_device_descriptors(self) -> list[CaptureDeviceDescriptor]:
        return []


class ReplayMicrophoneEnumerator(MicrophoneEnumeratorPort):
    """リプレイ実行では実機マイクを列挙しない。"""

    def list_microphones(self) -> list[str]:
        return []

    def find_microphone_index(self, device_name: str) -> int | None:
        del device_name
        return None


class ReplayPower(PowerPort):
    """リプレイ実行で OS の電源状態を変更しない。"""

    async def sleep(self) -> None:
        raise RuntimeError(
            "SPLAT_REPLAY_RUNTIME_PROFILE=replay では電源操作を実行できません"
        )
