"""録画操作コントロールウィジェット (ModernTheme 対応 ttk 版)"""

from __future__ import annotations

from typing import Optional

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox

from splat_replay.domain.services import RecordState
from splat_replay.gui.components.fade_label import FadeLabel
from splat_replay.gui.components.toggle_tooltip import ToggleToolTip
from splat_replay.gui.utils.application_controller import (
    GUIApplicationController,
)
from splat_replay.shared.logger import get_logger


class RecordingControlsWidget:
    """録画開始/停止/一時停止/再開を提供する操作パネル"""

    def __init__(
        self,
        button_area: ttk.Frame,
        controller: GUIApplicationController,
    ) -> None:
        self.logger = get_logger()
        self.button_area = button_area
        self.controller = controller

        self.timer_job: Optional[str] = None
        self.record_state = self.controller.get_current_record_state()
        self.controller.add_record_state_changed_listener(
            self._on_state_change
        )
        self.controller.add_auto_recorder_operation_state_listener(
            self._on_auto_recorder_operation_state_changed
        )

        # ステータス表示管理用
        self._status_queue: list[str] = []
        self._status_timer_job: Optional[str] = None
        self._status_displaying: bool = False

        # レイアウト構築 & 初期状態反映
        self._setup_buttons()
        self.logger.info("RecordingControlsWidget が初期化されました")

    def _setup_buttons(self) -> None:
        # 各ボタン生成（初期状態では pack せず、状態更新で配置）
        self.start_button = ttk.Button(
            self.button_area,
            text="⏺️ 録画開始",
            command=self.start_recording,
            bootstyle="info-outline",  # type: ignore
            width=15,
        )
        self.start_button_tooltip = ToggleToolTip(
            self.start_button,
            enabled=False,
            padding=3,
            bootstyle="light",  # type: ignore
        )

        self.pause_button = ttk.Button(
            self.button_area,
            text="⏸️ 一時停止",
            command=self.pause_recording,
            bootstyle="info-outline",  # type: ignore
            width=15,
        )
        self.pause_button_tooltip = ToggleToolTip(
            self.pause_button,
            enabled=False,
            padding=3,
            bootstyle="light",  # type: ignore
        )

        self.resume_button = ttk.Button(
            self.button_area,
            text="▶️ 再開",
            command=self.resume_recording,
            bootstyle="info-outline",  # type: ignore
            width=15,
        )
        self.resume_button_tooltip = ToggleToolTip(
            self.resume_button,
            enabled=False,
            padding=3,
            bootstyle="light",  # type: ignore
        )

        self.stop_button = ttk.Button(
            self.button_area,
            text="⏹️ 停止",
            command=self.stop_recording,
            bootstyle="info-outline",  # type: ignore
            width=15,
        )
        self.stop_button_tooltip = ToggleToolTip(
            self.stop_button,
            enabled=False,
            padding=3,
            bootstyle="light",  # type: ignore
        )

        self.status_label = FadeLabel(
            self.button_area,
            text="",
            justify="right",
            anchor="e",
            bootstyle="light",  # type: ignore
            duration=50,
        )
        self.status_label.pack(side="right", fill="x", padx=5, expand=False)

        self.update_button_states()

    def start_recording(self) -> None:
        def on_complete(result: bool):
            if result:
                self.logger.info("手動録画が正常に開始されました")
                return

            self.logger.warning("手動録画の開始に失敗しました")
            Messagebox.show_warning(
                "録画の開始に失敗しました。",
                "警告",
                parent=self.button_area,
            )

        self.controller.start_manual_recording(on_complete)

    def stop_recording(self) -> None:
        def on_complete(result: bool):
            if result:
                self.logger.info("手動録画が正常に停止されました")
                return

            self.logger.warning("手動録画の停止に失敗しました")
            Messagebox.show_warning(
                "録画の停止に失敗しました。",
                "警告",
                parent=self.button_area,
            )

        self.controller.stop_manual_recording(on_complete)

    def pause_recording(self) -> None:
        def on_complete(result: bool):
            if result:
                self.logger.info("手動録画が正常に一時停止されました")
                return

            self.logger.warning("手動録画の一時停止に失敗しました")
            Messagebox.show_warning(
                "録画の一時停止に失敗しました。",
                "警告",
                parent=self.button_area,
            )

        self.controller.pause_manual_recording(on_complete)

    def resume_recording(self) -> None:
        def on_complete(result: bool):
            if result:
                self.logger.info("手動録画が正常に再開されました")
                return

            Messagebox.show_warning(
                "録画の再開に失敗しました。",
                "警告",
                parent=self.button_area,
            )

        self.controller.resume_manual_recording(on_complete)

    def _on_state_change(self, state: RecordState) -> None:
        self.record_state = state
        self.update_button_states()

    def _on_auto_recorder_operation_state_changed(self, state: str) -> None:
        self._status_queue.append(state)
        if not self._status_displaying:
            self._show_next_status()

    def _show_next_status(self) -> None:
        if not self._status_queue:
            self._status_displaying = False
            self.status_label.fade_out()
            return
        self._status_displaying = True
        current_status = self._status_queue.pop(0)
        self.status_label.fade_in(text=current_status)

        # 3秒後に消す
        if self._status_timer_job:
            self.button_area.after_cancel(self._status_timer_job)
        self._status_timer_job = self.button_area.after(
            5000, lambda: self._clear_status(current_status)
        )

        # 1秒後に次のステータスがあれば表示
        def show_next_if_queued():
            if self._status_queue:
                self._show_next_status()

        self.button_area.after(1000, show_next_if_queued)

    def _clear_status(self, status: str) -> None:
        # 3秒経過後、表示中のステータスが同じなら消す
        if self.status_label.cget("text") == status:
            self.status_label.config(text="")
        self._status_displaying = False
        self._status_timer_job = None

    def update_button_states(self) -> None:
        """ボタンの表示/非表示を状態に合わせて再配置"""

        def show(button: ttk.Button, tooltip: ToggleToolTip) -> None:
            button.config(state="normal")
            button.pack(side="left", padx=(0, 10))
            tooltip.enabled = False

        def hide(button: ttk.Button, tooltip: ToggleToolTip) -> None:
            button.config(state="disabled")
            button.pack_forget()
            tooltip.enabled = False

        def disable(
            button: ttk.Button, tooltip: ToggleToolTip, tooltip_text: str
        ) -> None:
            button.config(state="disabled")
            button.pack(side="left", padx=(0, 10))
            tooltip.enabled = True
            tooltip.text = tooltip_text

        if self.record_state == RecordState.STOPPED:
            show(self.start_button, self.start_button_tooltip)
            hide(self.pause_button, self.pause_button_tooltip)
            hide(self.resume_button, self.resume_button_tooltip)
            hide(self.stop_button, self.stop_button_tooltip)
        elif self.record_state == RecordState.RECORDING:
            hide(self.start_button, self.start_button_tooltip)
            show(self.pause_button, self.pause_button_tooltip)
            hide(self.resume_button, self.resume_button_tooltip)
            show(self.stop_button, self.stop_button_tooltip)
        elif self.record_state == RecordState.PAUSED:
            hide(self.start_button, self.start_button_tooltip)
            hide(self.pause_button, self.pause_button_tooltip)
            show(self.resume_button, self.resume_button_tooltip)
            show(self.stop_button, self.stop_button_tooltip)
