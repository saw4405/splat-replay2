"""設定画面 (ModernTheme 適用版)

config/settings.toml の設定を GUI で編集する。
SettingsFieldFactory が返す (widget, var) 形式にも対応。
"""

from __future__ import annotations

import tkinter as tk
from typing import Dict, Optional, Tuple, cast

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Dialog, Messagebox
from ttkbootstrap.tooltip import ToolTip

from splat_replay.gui.dialogs.settings_field_factory import (
    FieldWidgetReturn,
    SettingsFieldFactory,
)
from splat_replay.gui.utils.application_controller import (
    GUIApplicationController,
)
from splat_replay.gui.utils.settings_controller import (
    GUISettingsController,
    SettingItemType,
)
from splat_replay.shared.logger import get_logger


class SettingsDialog(Dialog):
    """設定ダイアログ

    親ウィンドウ(MainWindow)の WM_DELETE_WINDOW を書き換えないよう注意。
    """

    field_widgets: Dict[str, Dict[str, FieldWidgetReturn]]

    def __init__(
        self, window: ttk.Window, controller: GUIApplicationController
    ) -> None:
        super().__init__(window, title="設定")
        self.logger = get_logger()
        self.window = window
        self.controller = controller
        self.settings_controller = GUISettingsController()
        self.field_widgets = {}
        self._closed = False
        self.logger.info("設定ダイアログが初期化されました")

    def create_body(self, master: tk.Widget):
        container = ttk.Frame(master, padding=10)
        container.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(side="top", fill="both", expand=True)
        self._create_tabs()

        # 自身の Toplevel に閉じるプロトコルを設定
        toplevel = master.winfo_toplevel()
        toplevel.protocol("WM_DELETE_WINDOW", self._on_closing)

    def create_buttonbox(self, master: tk.Widget):
        buttonbox = ttk.Frame(master)
        buttonbox.pack(side="bottom", fill="x", pady=10)

        ttk.Button(
            buttonbox,
            text="保存",
            command=self._on_save,
            bootstyle="primary-outline",  # type: ignore[arg-type]
        ).pack(side="right", padx=10)

        ttk.Button(
            buttonbox,
            text="閉じる",
            command=self._on_close,
            bootstyle="secondary-outline",  # type: ignore[arg-type]
        ).pack(side="right", padx=10)

    def _create_tabs(self) -> None:
        sections = self.settings_controller.get_all_sections()
        for section_id, display_name in sections.items():
            tab_frame = ttk.Frame(self.notebook)
            self.notebook.add(tab_frame, text=display_name, padding=(10, 10))
            self._create_section_fields(tab_frame, section_id)

    def _create_section_fields(
        self, parent: ttk.Frame, section_id: str
    ) -> None:
        try:
            colors = cast(ttk.Colors, ttk.Style().colors)

            section_data: Dict[str, Dict[str, SettingItemType]] = (
                self.settings_controller.get_section_data(section_id)
            )

            canvas = tk.Canvas(
                parent,
                bg=colors.bg,
                highlightthickness=0,
                borderwidth=0,
                relief="flat",
            )
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

            self.field_widgets[section_id] = {}
            row = 0
            for field_id, field_data in section_data.items():
                label = field_data["label"]
                help = str(field_data["help"])
                type = str(field_data["type"])
                choices = field_data["choices"]
                choices = choices if isinstance(choices, list) else None
                value = field_data["value"]
                recommended = bool(field_data["recommended"])
                label = ttk.Label(
                    scrollable_frame,
                    text=f"{label}",
                )
                label.grid(row=row, column=0, sticky="w", padx=10, pady=3)

                fw = SettingsFieldFactory.create_field(
                    scrollable_frame,
                    field_id,
                    type,
                    choices,
                    value,
                    recommended,
                )
                widget_for_layout = fw[0] if isinstance(fw, tuple) else fw
                widget_for_layout.grid(
                    row=row, column=1, sticky="ew", padx=10, pady=5
                )
                ToolTip(
                    widget_for_layout,
                    text=help,
                    padding=3,
                    bootstyle="light",  # type: ignore
                )
                self.field_widgets[section_id][field_id] = fw
                row += 1

            scrollable_frame.columnconfigure(1, weight=1)
            canvas.pack(side="left", fill="both", expand=True)
            # scrollbar.pack(side="right", fill="y")

            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            canvas.bind("<MouseWheel>", _on_mousewheel)
        except Exception as e:
            self.logger.error(
                f"セクション '{section_id}' のフィールド作成でエラー: {e}"
            )

    def _on_save(self) -> None:
        success, error_message = self._apply_settings()
        if not success:
            Messagebox.show_error(
                error_message,
                "検証エラー",
                alert=True,
            )
            return

        self.settings_controller.save()
        self.logger.info("設定が保存されました")
        Messagebox.show_info("設定が保存されました。", "完了")
        self.close()

    def _apply_settings(self) -> Tuple[bool, Optional[str]]:
        for section_id, field_widgets in self.field_widgets.items():
            section_data = {}
            for field_id, widget in field_widgets.items():
                value = SettingsFieldFactory.get_widget_value(widget)
                field_type = self.settings_controller.get_type(
                    section_id, field_id
                )
                is_valid, error_message = (
                    SettingsFieldFactory.validate_field_value(
                        field_id, value, field_type
                    )
                )
                if not is_valid:
                    return False, f"{field_id}: {error_message}"

                section_data[field_id] = value
            self.settings_controller.update_section_data(
                section_id, section_data
            )
        return True, None

    def _on_close(self) -> None:
        try:
            if self.has_unsaved_changes():
                result = Messagebox.yesno(
                    "変更が保存されていません。保存せずに閉じますか？", "確認"
                )
                if result is None or result != "はい":
                    return
            self.close()
        except Exception as e:
            self.logger.error(f"設定キャンセルでエラー: {e}")

    def has_unsaved_changes(self) -> bool:
        # 適用できないということは入力中の値が不正ということ
        if not self.field_widgets:
            return False
        success, _ = self._apply_settings()
        if not success:
            return True

        return self.settings_controller.has_changes()

    def _on_closing(self) -> None:
        self._on_close()

    def close(self) -> None:
        if self._closed:
            return

        if not self._toplevel:
            raise Exception("Dialog is not initialized")

        self._toplevel.after_idle(self._toplevel.destroy)
        self.field_widgets.clear()
        self._closed = True
