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
        self._closed = False

        self.logger.info("メタデータ編集ダイアログが初期化されました")

    def create_body(self, master: tk.Widget):
        container = ttk.Frame(master, padding=10)
        container.pack(fill="both", expand=True)
        self.form = MetadataEditorForm(container, self.metadata)

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

    def _on_save(self) -> None:
        self._result = self.form.get_metadata()
        self.close()

    def _on_close(self) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return

        if not self._toplevel:
            raise Exception("Dialog is not initialized")

        self._toplevel.after_idle(self._toplevel.destroy)
        self._closed = True
