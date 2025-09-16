from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox, MessageDialog
from ttkbootstrap.tableview import Tableview

from splat_replay.domain.models import BattleResult, VideoAsset
from splat_replay.gui.components.toggle_tooltip import ToggleToolTip
from splat_replay.gui.utils.application_controller import (
    GUIApplicationController,
)
from splat_replay.gui.widgets.card_widget import CardWidget


class VideoListCard(CardWidget):
    """動画リスト（録画済み/編集済みのタブ表示）"""

    def __init__(
        self,
        parent: ttk.Frame,
        controller: GUIApplicationController,
        show_edit_dialog: Callable[
            [Dict[str, str | None]], Optional[Dict[str, str]]
        ],
        upload_start_callback: Callable[[], None],
    ) -> None:
        title = "　🎦 動画リスト　"
        super().__init__(parent, title)
        self.controller = controller
        self.show_edit_dialog = show_edit_dialog
        self.upload_start_callback = upload_start_callback

        self._setup_toolbar()
        self._setup_video_table()

        # 初期データ読み込み
        self.refresh_list()

        # 動画アセットイベントを購読して自動リフレッシュ
        self._debounce_job: str | None = None

        def _on_asset_event(event_type: str, _payload: dict) -> None:
            # 連続イベントを 500ms デバウンス
            if self._debounce_job is not None:
                try:
                    self.header.after_cancel(self._debounce_job)
                except Exception:
                    pass

            def _do_refresh() -> None:
                self.refresh_list()

            try:
                self._debounce_job = self.header.after(500, _do_refresh)
            except Exception:
                _do_refresh()

        controller.add_asset_event_listener(_on_asset_event)

    def _setup_toolbar(self) -> None:
        self.refresh_button = ttk.Button(
            self.header,
            text="🔄 更新",
            command=self.refresh_list,
            width=15,
            bootstyle="info-outline",  # type: ignore
        )
        self.refresh_button.pack(side="left", padx=(0, 10))

        self.folder_button = ttk.Button(
            self.header,
            text="📂 フォルダーを開く",
            command=self.open_video_folder,
            width=18,
            bootstyle="info-outline",  # type: ignore
        )
        self.folder_button.pack(side="left", padx=(0, 10))

        self.play_button = ttk.Button(
            self.header,
            text="▶ 再生",
            command=self._play_clicked,
            width=15,
            state="disabled",
            bootstyle="info-outline",  # type: ignore
        )
        self.play_button.pack(side="left", padx=(0, 10))
        self.play_button_tooltip = ToggleToolTip(
            self.play_button,
            text="動画を一つのみ選択してください",
            padding=3,
            enabled=False,
            bootstyle="light",  # type: ignore
        )

        self.edit_button = ttk.Button(
            self.header,
            text="✏ 編集",
            command=self._edit_clicked,
            width=15,
            state="disabled",
            bootstyle="info-outline",  # type: ignore
        )
        self.edit_button.pack(side="left", padx=(0, 10))
        self.edit_button_tooltip = ToggleToolTip(
            self.edit_button,
            text="動画を一つのみ選択してください",
            padding=3,
            enabled=False,
            bootstyle="light",  # type: ignore
        )

        self.delete_button = ttk.Button(
            self.header,
            text="🗑 削除",
            command=self._delete_clicked,
            width=15,
            state="disabled",
            bootstyle="info-outline",  # type: ignore
        )
        self.delete_button.pack(side="left")
        self.delete_button_tooltip = ToggleToolTip(
            self.delete_button,
            text="動画を選択してください",
            padding=3,
            enabled=False,
            bootstyle="light",  # type: ignore
        )

        self.upload_button = ttk.Button(
            self.header,
            text="☁ 編集＆アップロード",
            command=self.upload_start_callback,
            width=20,
            state="disabled",
            bootstyle="primary-outline",  # type: ignore
        )
        self.upload_button.pack(side="right", padx=(10, 0))
        self.upload_button_tooltip = ToggleToolTip(
            self.upload_button,
            text="動画がありません",
            padding=3,
            enabled=False,
            bootstyle="light",  # type: ignore
        )

    def _setup_video_table(self) -> None:
        columns = [
            {"text": "日時", "width": 250, "minwidth": 150, "stretch": False},
            {
                "text": "マッチ",
                "width": 200,
                "minwidth": 100,
                "stretch": False,
            },
            {
                "text": "ルール",
                "width": 150,
                "minwidth": 100,
                "stretch": False,
            },
            {"text": "レート", "width": 100, "minwidth": 80, "stretch": False},
            {"text": "結果", "width": 80, "minwidth": 50, "stretch": False},
            {
                "text": "ステージ",
                "width": 200,
                "minwidth": 100,
                "stretch": False,
            },
            {"text": "キル数", "width": 80, "minwidth": 50, "stretch": False},
            {"text": "デス数", "width": 80, "minwidth": 50, "stretch": False},
            {
                "text": "スペシャル使用回数",
                "width": 80,
                "minwidth": 50,
                "stretch": False,
            },
            {"text": "長さ", "width": 100, "minwidth": 60, "stretch": False},
            {
                "text": "ファイルパス",
                "width": 100,
                "minwidth": 100,
                "stretch": True,
            },
        ]

        # Notebook for tabs
        self.tabs = ttk.Notebook(self.content)
        self.tabs.pack(fill="both", expand=True)

        # Recorded tab
        self._recorded_tab = ttk.Frame(self.tabs)
        self.tabs.add(self._recorded_tab, text="録画済み")
        self.recorded_table = Tableview(
            self._recorded_tab,
            coldata=columns,
            paginated=False,
            searchable=False,
            yscrollbar=True,
            bootstyle="dark",
        )
        self.recorded_table.pack(fill="both", expand=True)
        self.recorded_table.view.bind(
            "<<TreeviewSelect>>", self._on_selection_changed
        )
        self.recorded_table.view.bind(
            "<Double-1>", self._on_double_click_recorded
        )

        # Edited tab
        self._edited_tab = ttk.Frame(self.tabs)
        self.tabs.add(self._edited_tab, text="編集済み")
        self.edited_table = Tableview(
            self._edited_tab,
            coldata=columns,
            paginated=False,
            searchable=False,
            yscrollbar=True,
            bootstyle="dark",
        )
        self.edited_table.pack(fill="both", expand=True)
        self.edited_table.view.bind(
            "<<TreeviewSelect>>", self._on_selection_changed
        )
        self.edited_table.view.bind("<Double-1>", self._on_double_click_edited)

        # Tab change -> update toolbar states
        self.tabs.bind(
            "<<NotebookTabChanged>>",
            lambda _e: self._on_selection_changed(None),
        )

    def _on_reset(self) -> None:
        self.refresh_list()

    def refresh_list(self) -> None:
        self.refresh_recorded_list()
        self.refresh_edited_list()

    def refresh_recorded_list(self) -> None:
        def on_complete(
            video_assets_with_length: List[Tuple[VideoAsset, float | None]],
        ) -> None:
            rows = [
                self._convert_to_row(asset, length)
                for asset, length in video_assets_with_length
            ]
            self.recorded_table.delete_rows()
            self.recorded_table.insert_rows("end", rows)
            # enable upload if recorded exists
            if self.recorded_table.get_rows():
                self.upload_button.config(state="normal")
                self.upload_button_tooltip.disable()
            else:
                self.upload_button.config(state="disabled")
                self.upload_button_tooltip.enable()
            self._on_selection_changed(None)

        self.controller.get_video_assets_with_length(on_complete)

    def refresh_edited_list(self) -> None:
        def on_complete(
            items: List[Tuple[Path, float | None, dict[str, str] | None]],
        ) -> None:
            rows = [
                self._convert_edited_to_row(path, length, md)
                for (path, length, md) in items
            ]
            self.edited_table.delete_rows()
            self.edited_table.insert_rows("end", rows)
            self._on_selection_changed(None)

        self.controller.get_edited_assets_with_length(on_complete)

    def _convert_to_row(
        self, asset: VideoAsset, video_length: float | None
    ) -> Tuple[str, ...]:
        video_path = str(asset.video) if asset.video else "不明"

        date_str = "未開始"
        rate_str = "未検出"
        judgement_str = "未判定"
        match_str = "未取得"
        rule_str = "未取得"
        stage_str = "未取得"
        kill_str = "未取得"
        death_str = "未取得"
        special_str = "未取得"

        if asset.metadata:
            if asset.metadata.started_at:
                date_str = asset.metadata.started_at.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            if asset.metadata.rate:
                rate_str = str(asset.metadata.rate)
            if asset.metadata.judgement:
                judgement_str = asset.metadata.judgement.value

            if isinstance(asset.metadata.result, BattleResult):
                match_str = str(asset.metadata.result.match.value)
                rule_str = str(asset.metadata.result.rule.value)
                stage_str = str(asset.metadata.result.stage.value)
                kill_str = str(asset.metadata.result.kill)
                death_str = str(asset.metadata.result.death)
                special_str = str(asset.metadata.result.special)

        if video_length:
            minutes, seconds = divmod(video_length, 60)
            minutes = int(minutes)
            seconds = int(seconds)
            duration_str = f"{minutes:02d}:{seconds:02d}"
        else:
            duration_str = "不明"

        return (
            date_str,
            match_str,
            rule_str,
            rate_str,
            judgement_str,
            stage_str,
            kill_str,
            death_str,
            special_str,
            duration_str,
            video_path,
        )

    def _convert_edited_to_row(
        self,
        video_path: Path,
        video_length: float | None,
        metadata: dict[str, str] | None,
    ) -> Tuple[str, ...]:
        date_str = (metadata or {}).get("started_at") or "未開始"
        match_str = (metadata or {}).get("match") or "未取得"
        rule_str = (metadata or {}).get("rule") or "未取得"
        rate_str = (metadata or {}).get("rate") or "未検出"
        judgement_str = (metadata or {}).get("judgement") or "未判定"
        stage_str = (metadata or {}).get("stage") or "未取得"
        kill_str = (metadata or {}).get("kill") or "未取得"
        death_str = (metadata or {}).get("death") or "未取得"
        special_str = (metadata or {}).get("special") or "未取得"

        if video_length:
            minutes, seconds = divmod(video_length, 60)
            minutes = int(minutes)
            seconds = int(seconds)
            duration_str = f"{minutes:02d}:{seconds:02d}"
        else:
            duration_str = "不明"

        return (
            date_str,
            match_str,
            rule_str,
            rate_str,
            judgement_str,
            stage_str,
            str(kill_str),
            str(death_str),
            str(special_str),
            duration_str,
            str(video_path),
        )

    def _get_active_table(self) -> Tableview:
        current = self.tabs.index(self.tabs.select())
        return self.edited_table if current == 1 else self.recorded_table

    def _is_edited_tab_active(self) -> bool:
        return self.tabs.index(self.tabs.select()) == 1

    def _on_selection_changed(self, _event) -> None:
        table = self._get_active_table()
        selected_rows = table.get_rows(selected=True)

        can_single = len(selected_rows) == 1
        can_any = len(selected_rows) > 0

        if self._is_edited_tab_active():
            self.edit_button.config(state="disabled")
            self.edit_button_tooltip.enable()
        else:
            if can_single:
                self.edit_button.config(state="normal")
                self.edit_button_tooltip.disable()
            else:
                self.edit_button.config(state="disabled")
                self.edit_button_tooltip.enable()

        if can_single:
            self.play_button.config(state="normal")
            self.play_button_tooltip.disable()
        else:
            self.play_button.config(state="disabled")
            self.play_button_tooltip.enable()

        if can_any:
            self.delete_button.config(state="normal")
            self.delete_button_tooltip.disable()
        else:
            self.delete_button.config(state="disabled")
            self.delete_button_tooltip.enable()

    def _on_double_click_recorded(self, event) -> None:
        iid = event.widget.identify_row(event.y)
        if not iid:
            return
        row = self.recorded_table.iidmap.get(iid)
        if not row:
            return
        video_path = row.values[-1]
        self._play_video(Path(video_path))

    def _on_double_click_edited(self, event) -> None:
        iid = event.widget.identify_row(event.y)
        if not iid:
            return
        row = self.edited_table.iidmap.get(iid)
        if not row:
            return
        video_path = row.values[-1]
        self._play_video(Path(video_path))

    def _play_clicked(self) -> None:
        video_paths = self.get_selected_video_paths()
        if len(video_paths) != 1:
            return
        self._play_video(video_paths[0])

    def _play_video(self, path: Path) -> None:
        if not path.exists():
            return
        os.startfile(path)

    def _show_edit_dialog(
        self, metadata: Dict[str, str | None], video_path: Path
    ) -> Optional[Dict[str, str]]:
        result = self.show_edit_dialog(metadata)
        if result:

            def on_complete(success: bool) -> None:
                if not success:
                    Messagebox.show_warning(
                        "メタデータの保存に失敗しました",
                        title="エラー",
                        parent=self.parent,
                        alert=True,
                    )

            self.controller.save_metadata(video_path, result, on_complete)
        return result

    def _edit_clicked(self) -> None:
        # 編集タブは非対応（UIで無効化済み）
        video_paths = self.get_selected_video_paths()
        if len(video_paths) != 1:
            return

        def on_complete(metadata: Optional[Dict[str, str | None]]) -> None:
            if not metadata:
                return
            self._show_edit_dialog(metadata, video_paths[0])

        self.controller.get_metadata(video_paths[0], on_complete)

    def _delete_clicked(self) -> None:
        video_paths = self.get_selected_video_paths()
        if len(video_paths) <= 0:
            return

        file_list: List[str] = [f" * {p.name}" for p in video_paths]
        dialog = MessageDialog(
            f"以下の動画を削除しますか？\n{chr(10).join(file_list)}",
            title="確認",
            buttons=["閉じる", "削除:danger"],
            parent=self.parent,
        )
        dialog.show()
        if dialog.result != "削除":
            return

        def on_complete() -> None:
            self.refresh_list()

        if self._is_edited_tab_active():
            for video_path in video_paths:
                self.controller.delete_edited_asset(video_path, on_complete)
        else:
            for video_path in video_paths:
                self.controller.delete_video_assets(video_path, on_complete)

    def get_selected_video_paths(self) -> List[Path]:
        table = self._get_active_table()
        selected_rows = table.get_rows(selected=True)
        paths: List[Path] = []
        for row in selected_rows:
            video_path = row.values[-1]
            if video_path:
                paths.append(Path(video_path))
        return paths

    def open_video_folder(self) -> None:
        def open_dir(folder_path: Path | None, warn_title: str) -> None:
            if not folder_path or not folder_path.exists():
                Messagebox.show_warning(
                    warn_title,
                    title="エラー",
                    parent=self.parent,
                    alert=True,
                )
                return
            subprocess.Popen(["explorer", folder_path], shell=True)

        if self._is_edited_tab_active():
            self.controller.get_edited_dir(
                lambda p: open_dir(p, "編集ディレクトリが存在しません")
            )
        else:
            self.controller.get_recorded_dir(
                lambda p: open_dir(p, "録画ディレクトリが存在しません")
            )

    def copy_video_path(self) -> None:
        video_paths = self.get_selected_video_paths()
        if len(video_paths) != 1:
            return
        self.parent.clipboard_clear()
        self.parent.clipboard_append(str(video_paths[0]))
