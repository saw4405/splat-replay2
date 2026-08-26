"""Switch 電源監視の状態モデル。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class SwitchPowerState(str, Enum):
    """自動録画が認識している Switch 電源状態。"""

    UNKNOWN = "unknown"
    ARMED = "armed"
    WAITING_FOR_POWER_ON = "waiting_for_power_on"
    CAPTURE_DISCONNECTED = "capture_disconnected"
    STOPPED = "stopped"


@dataclass(frozen=True)
class SwitchPowerMonitor:
    """有効なフレームの連続観測から電源状態を遷移させる。"""

    state: SwitchPowerState = SwitchPowerState.UNKNOWN
    off_threshold: int = 3
    on_threshold: int = 3
    consecutive_off: int = 0
    consecutive_on: int = 0

    def __post_init__(self) -> None:
        if self.off_threshold <= 0:
            raise ValueError("off_threshold は1以上である必要があります")
        if self.on_threshold <= 0:
            raise ValueError("on_threshold は1以上である必要があります")

    def observe(
        self, *, power_is_off: bool
    ) -> tuple[SwitchPowerMonitor, bool]:
        """一回の有効なフレーム観測を適用する。

        Returns:
            更新後の状態と、今回の遷移で後処理要求を発行するか。
        """
        if self.state is SwitchPowerState.STOPPED:
            return self, False

        if power_is_off:
            observed = replace(
                self,
                consecutive_off=self.consecutive_off + 1,
                consecutive_on=0,
            )
            if observed.consecutive_off < observed.off_threshold:
                return observed, False
            if observed.state is SwitchPowerState.ARMED:
                return (
                    replace(
                        observed,
                        state=SwitchPowerState.WAITING_FOR_POWER_ON,
                        consecutive_off=0,
                    ),
                    True,
                )
            if observed.state is SwitchPowerState.UNKNOWN:
                return (
                    replace(
                        observed,
                        state=SwitchPowerState.WAITING_FOR_POWER_ON,
                        consecutive_off=0,
                    ),
                    False,
                )
            return replace(observed, consecutive_off=0), False

        observed = replace(
            self,
            consecutive_off=0,
            consecutive_on=self.consecutive_on + 1,
        )
        if observed.consecutive_on < observed.on_threshold:
            return observed, False
        if observed.state in {
            SwitchPowerState.UNKNOWN,
            SwitchPowerState.WAITING_FOR_POWER_ON,
            SwitchPowerState.CAPTURE_DISCONNECTED,
        }:
            return (
                replace(
                    observed,
                    state=SwitchPowerState.ARMED,
                    consecutive_on=0,
                ),
                False,
            )
        return replace(observed, consecutive_on=0), False

    def disconnect(self) -> SwitchPowerMonitor:
        """キャプチャーデバイス切断をSwitch電源OFFと分けて記録する。"""
        return replace(
            self,
            state=SwitchPowerState.CAPTURE_DISCONNECTED,
            consecutive_off=0,
            consecutive_on=0,
        )

    def stop(self) -> SwitchPowerMonitor:
        """明示停止状態へ遷移する。"""
        return replace(
            self,
            state=SwitchPowerState.STOPPED,
            consecutive_off=0,
            consecutive_on=0,
        )
