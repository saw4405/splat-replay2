"""録画を優先し、後処理も完了したフレーム境界で更新を許可する。"""

from __future__ import annotations

from collections.abc import Callable

from splat_replay.application.services.process.auto_process_service import (
    AutoProcessService,
)
from splat_replay.application.use_cases.auto_recording_use_case import (
    AutoRecordingUseCase,
)
from splat_replay.domain.models.switch_power import SwitchPowerState


class DesktopMaintenance:
    def __init__(
        self,
        recording: AutoRecordingUseCase,
        processing: AutoProcessService,
        requested: Callable[[], bool],
        ready: Callable[[], None],
        can_enter: Callable[[], bool] = lambda: True,
        quitting: Callable[[], bool] = lambda: False,
    ) -> None:
        self.recording = recording
        self.processing = processing
        self.requested = requested
        self.ready = ready
        self.entered = False
        self.can_enter = can_enter
        self.quitting = quitting

    def check(self) -> bool:
        """await を挟まず、完了判定と新規処理の受付停止を確定する。"""
        pending = self.requested()
        self.processing.update_pending = pending
        if not pending:
            self.entered = False
            self.processing.start_edit_upload_uc.maintenance = False
            return False
        if self.entered:
            self.ready()
            return True
        if (
            (
                self.quitting()
                or self.recording.power_status()
                in {
                    SwitchPowerState.WAITING_FOR_POWER_ON,
                    SwitchPowerState.CAPTURE_DISCONNECTED,
                }
            )
            and self.processing.power_off_count
            >= self.recording.power_off_count
            and self.processing.is_idle()
            and self.can_enter()
        ):
            self.processing.start_edit_upload_uc.maintenance = True
            self.entered = True
            self.ready()
            return True
        return False
