"""メタデータ編集ウィジェット.

AutoRecorder の状態をリアルタイム表示し、メタデータを編集する。
"""

from __future__ import annotations

import tkinter as tk
from typing import Dict

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Dialog

from splat_replay.gui.widgets.metadata_editor_form import MetadataEditorForm
from splat_replay.shared.logger import get_logger


class MetadataEditorDialog(Dialog):
    """メタデータ編集ウィジェット（AutoRecorder の状態をリアルタイム表示）"""

    def __init__(
        self,
        window: ttk.Window,
        metadata: Dict[str, str | None],
    ) -> None:
        super().__init__(
            window,
            title="メタデータ編集",
        )
        self.logger = get_logger()
        self.window = window
        self.metadata = metadata

        self.logger.info("MetadataEditorDialog が初期化されました")

    def create_body(self, master: tk.Widget):
        container = ttk.Frame(master)
        container.pack(fill="x", expand=True)
        self.form = MetadataEditorForm(container, self.metadata)

    def create_buttonbox(self, master: tk.Widget):
        container = ttk.Frame(master)
        container.pack(fill="x", expand=True)

        ttk.Button(
            container,
            text="保存",
            command=self.save,
            bootstyle="primary",  # type: ignore
        ).pack(side="right", padx=5, pady=5)

        ttk.Button(
            container,
            text="閉じる",
            command=self.close,
            bootstyle="secondary",  # type: ignore
        ).pack(side="right", padx=5, pady=5)

    def save(self) -> None:
        self._result = self.form.get_metadata()
        self.close()

    def close(self) -> None:
        if self._toplevel:
            self._toplevel.after_idle(self._toplevel.destroy)
