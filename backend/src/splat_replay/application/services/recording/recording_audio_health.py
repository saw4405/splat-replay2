"""OBS 音声状態の確認と継続観測。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable

from splat_replay.application.interfaces import (
    AudioInputHealthCheckResult,
    CaptureDevicePort,
    ConfigPort,
    LoggerPort,
    VideoRecorderPort,
)
from splat_replay.domain.models import SwitchPowerState


class RecordingAudioHealthService:
    """入力準備状態を確認し、OBS 音声状態を観測する。"""

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

    async def check(
        self, *, sample_duration_seconds: float
    ) -> AudioInputHealthCheckResult:
        """単発で音声状態を確認する。無音でも録画や OBS を操作しない。"""
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
        return result

    async def observe(
        self,
    ) -> AsyncGenerator[AudioInputHealthCheckResult, None]:
        """OBS 音声状態を連続して観測し、1秒窓ごとの結果を返す。"""
        input_name = self._config.get_capture_device_settings().name
        observations = self._recorder.observe_audio_input_health(input_name)
        try:
            async for result in observations:
                yield result
        finally:
            await observations.aclose()

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
