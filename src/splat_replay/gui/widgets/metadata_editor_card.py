"""メタデータ編集ウィジェット.

AutoRecorder の状態をリアルタイム表示し、メタデータを編集する。
"""

from __future__ import annotations

from typing import Dict, Optional

import ttkbootstrap as ttk

from splat_replay.domain.services import RecordState
from splat_replay.gui.controllers.application_controller import (
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
        self._reflesh_metadata()

        self.reset_button = ttk.Button(
            self.footer,
            text="リセット",
            width=15,
            command=self.reset,
            bootstyle="info-outline",  # type: ignore
        )
        self.reset_button.pack(side="left", padx=(0, 10))

        self.controller.add_record_state_changed_listener(
            self._on_record_state_changed
        )
        self.logger.info("MetadataEditorCard が初期化されました")

    def _on_record_state_changed(self, state: RecordState) -> None:
        if state != RecordState.STOPPED:
            return

    def reset(self) -> None:
        self.form.reset()
        self._reflesh_metadata()

    def _reflesh_metadata(self) -> None:
        def on_complete(metadata: Optional[Dict[str, str | None]]) -> None:
            self.form.update(metadata)
            self.content.after(500, self._reflesh_metadata)

        self.controller.get_current_metadata(on_complete)
