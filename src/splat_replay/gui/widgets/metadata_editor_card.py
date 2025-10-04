"""メタデータ編集ウィジェット.

AutoRecorder の状態をリアルタイム表示し、メタデータを編集する。
"""

from __future__ import annotations

from typing import Dict, Optional

import ttkbootstrap as ttk

from splat_replay.gui.utils.application_controller import (
    GUIApplicationController,
)
from splat_replay.gui.widgets.card_widget import CardWidget
from splat_replay.gui.widgets.metadata_editor_form import MetadataEditorForm


class MetadataEditorCard(CardWidget):
    """メタデータ編集ウィジェット（AutoRecorder の状態をリアルタイム表示）"""

    def __init__(
        self,
        parent: ttk.Frame,
        controller: GUIApplicationController,
    ) -> None:
        title = "　ℹ️ 録画情報　"
        super().__init__(parent, title)
        self.controller = controller

        self.form = MetadataEditorForm(self.content)

        self.reset_button = ttk.Button(
            self.footer,
            text="リセット",
            width=15,
            command=self.reset,
            bootstyle="info-outline",  # type: ignore
        )
        self.reset_button.pack(side="left", padx=(0, 10))

        self.reset()

        self.controller.add_record_reset_listener(self.reset)
        self.controller.add_metadata_listener(self._on_metadata_changed)
        self.logger.info("MetadataEditorCard が初期化されました")

    def _on_metadata_changed(
        self, metadata: Dict[str, str | int | None]
    ) -> None:
        self.form.update(metadata)

    def reset(self) -> None:
        self.form.reset()

        def on_complete(
            metadata: Optional[Dict[str, str | int | None]],
        ) -> None:
            self.form.update(metadata)

        self.controller.get_current_metadata(on_complete)
