"""OBS 音声ヘルスチェックと安全な復旧のオーケストレーション。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from splat_replay.application.interfaces import (
    AudioInputHealthCheckResult,
    CaptureDevicePort,
    ConfigPort,
    LoggerPort,
    VideoRecorderPort,
)
from splat_replay.domain.models import SwitchPowerState

RECOVERY_CONFIRMATION_SAMPLE_SECONDS = 1.0


class RecordingAudioHealthService:
    """実機入力の準備完了時だけ OBS の無音を復旧する。"""

    def __init__(
        self,
        recorder: VideoRecorderPort,
        capture_device: CaptureDevicePort,
        config: ConfigPort,
        power_state: Callable[[], SwitchPowerState],
        logger: LoggerPort,
    ) -> None:
        self._recorder = recorder
        self._capture_device = capture_device
        self._config = config
        self._power_state = power_state
        self._logger = logger

    async def check_and_recover(
        self, *, sample_duration_seconds: float
    ) -> AudioInputHealthCheckResult:
        """実機入力の準備完了後だけ音声を確認し、一度復旧する。"""
        input_name = self._config.get_capture_device_settings().name
        try:
            connected = await asyncio.to_thread(
                self._capture_device.is_connected
            )
        except Exception as exc:
            self._logger.warning(
                "キャプチャーデバイス状態を確認できないため OBS 音声検査をスキップします",
                error=str(exc),
            )
            return self._skipped(
                input_name, "キャプチャーデバイス状態を確認できません。"
            )
        if not connected:
            self._logger.info(
                "キャプチャーデバイス未接続のため OBS 音声検査をスキップします"
            )
            return self._skipped(
                input_name, "キャプチャーデバイスが接続されていません。"
            )

        try:
            power_state = self._power_state()
        except Exception as exc:
            self._logger.warning(
                "Switch 電源状態を確認できないため OBS 音声検査をスキップします",
                error=str(exc),
            )
            return self._skipped(
                input_name, "Switch 電源状態を確認できません。"
            )
        if power_state is not SwitchPowerState.ARMED:
            self._logger.info(
                "Switch が起動済みでないため OBS 音声検査をスキップします",
                power_state=power_state.value,
            )
            return self._skipped(
                input_name, "Switch の電源ONを待機しています。"
            )

        result = await self._recorder.check_audio_input_health(
            input_name,
            sample_duration_seconds=sample_duration_seconds,
        )
        if result.status != "silent":
            return result

        confirmation = await self._recorder.check_audio_input_health(
            input_name,
            sample_duration_seconds=max(
                sample_duration_seconds,
                RECOVERY_CONFIRMATION_SAMPLE_SECONDS,
            ),
        )
        if confirmation.status != "silent":
            return confirmation

        if not await self._recorder.try_recover_audio_input():
            return confirmation

        recovered = await self._recorder.check_audio_input_health(
            input_name,
            sample_duration_seconds=RECOVERY_CONFIRMATION_SAMPLE_SECONDS,
        )
        self._logger.info(
            "OBS 音声自動復旧後の再検査が完了しました",
            healthy=recovered.healthy,
            status=recovered.status,
        )
        return recovered

    @staticmethod
    def _skipped(input_name: str, details: str) -> AudioInputHealthCheckResult:
        return AudioInputHealthCheckResult(
            input_name=input_name,
            status="skipped",
            healthy=True,
            short_message="",
            details=details,
            peak_db=None,
        )
