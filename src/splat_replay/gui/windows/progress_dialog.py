"""Two-pane progress dialog for Editing and Uploading.

Left: 編雁Epane; Right: アチE�EローチEpane.
Each pane shows a large meter and a vertical list of items with checklists.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Dict, List, Optional, Tuple, cast

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Dialog
from ttkbootstrap.widgets import Meter

from splat_replay.gui.controllers.application_controller import (
    GUIApplicationController,
)
from splat_replay.gui.widgets.card_widget import CardWidget


class ProgressDialog(Dialog):
    """進捗ダイアログ: 左=編集 右=アップロード、"""

    EDIT_STEPS: List[Tuple[str, str]] = [
        ("edit_group", "グループ編集"),
        ("concat", "動画結合"),
        ("subtitle", "字幕結合"),
        ("metadata", "メタデータ編集"),
        ("thumbnail", "サムネイル編集"),
        ("volume", "音量調整"),
        ("save", "録画済動画削除・編集済動画保存"),
    ]

    UPLOAD_STEPS: List[Tuple[str, str]] = [
        ("collect", "ファイル情報収集"),
        ("upload", "動画アップロード"),
        ("caption", "字幕アップロード"),
        ("thumb", "サムネイルアップロード"),
        ("playlist", "プレイリストに追加"),
        ("delete", "編集済動画削除"),
    ]

    def __init__(
        self,
        window: ttk.Window,
        controller: GUIApplicationController,
        *,
        size: Tuple[int, int] | None = (1200, 1200),
    ) -> None:
        super().__init__(window, title="進捗ダイアログ")
        self.window = window
        self.controller = controller
        self._req_size = size

        # task states
        self._totals: Dict[str, int] = {"auto_edit": 0, "auto_upload": 0}
        self._completeds: Dict[str, int] = {"auto_edit": 0, "auto_upload": 0}
        self._ui_ready = False
        self._closed = False

        # UI panes set in create_body
        self._edit_pane: TaskPane | None = None
        self._upload_pane: TaskPane | None = None

        # current active item index per task
        self._active_index: Dict[str, int | None] = {
            "auto_edit": None,
            "auto_upload": None,
        }

        # finished flags to control cancel availability
        self._finished: Dict[str, bool] = {
            "auto_edit": False,
            "auto_upload": False,
        }

        # listen early
        self.controller.add_progress_listener(self._on_progress)

    # Dialog content
    def create_body(self, master: tk.Widget) -> None:  # type: ignore[override]
        container = ttk.Frame(master, padding=10)
        container.pack(fill="both", expand=True)

        try:
            if self._req_size:
                master.winfo_toplevel().geometry(
                    f"{self._req_size[0]}x{self._req_size[1]}"
                )
        except Exception:
            pass

        grid = ttk.Frame(container)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1, minsize=1000)
        grid.rowconfigure(0, weight=1, minsize=500)
        grid.rowconfigure(1, weight=1, minsize=500)

        # 左: 編集パネル
        left = ttk.Frame(grid, padding=8)
        left.grid(row=0, column=0, sticky="nsew")
        self._edit_pane = TaskPane(left, title="編集", steps=self.EDIT_STEPS)

        # 右: アップロードパネル
        right = ttk.Frame(grid, padding=8)
        right.grid(row=1, column=0, sticky="nsew")
        self._upload_pane = TaskPane(
            right, title="アップロード", steps=self.UPLOAD_STEPS
        )

        self._ui_ready = True

    def create_buttonbox(self, master: tk.Widget) -> None:
        buttonbox = ttk.Frame(master)
        buttonbox.pack(side="bottom", fill="x", pady=10)
        self.close_button = ttk.Button(
            buttonbox, text="閉じる", command=self._on_close, state=tk.DISABLED
        )
        self.close_button.pack(side="right", padx=10)
        self.cancel_button = ttk.Button(
            buttonbox,
            text="キャンセル",
            command=self._on_cancel,
            bootstyle="danger",  # type: ignore[arg-type]
        )
        self.cancel_button.pack(side="right", padx=10)

    def _on_close(self) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        try:
            assert self._toplevel is not None, "Dialog is not initialized"
            self._toplevel.after_idle(self._toplevel.destroy)
        finally:
            self._closed = True

    # ---- Event handling ----
    def _on_progress(self, event: dict) -> None:
        if not self._ui_ready:
            return

        task_id = str(event.get("task_id") or "")
        kind = str(event.get("kind") or "")

        pane = self._edit_pane if task_id == "auto_edit" else self._upload_pane
        if pane is None:
            return

        if kind == "start":
            total = int(event.get("total") or 0)
            self._totals[task_id] = total
            self._completeds[task_id] = 0
            pane.set_total(total)
            pane.set_completed(0)
            # add initial items if provided
            try:
                titles = event.get("items") or []
                for t in titles:
                    pane.add_item(str(t))
            except Exception:
                pass
            self._active_index[task_id] = None
        elif kind == "items":
            # explicit items list
            try:
                titles = event.get("items") or []
                for t in titles:
                    pane.add_item(str(t))
            except Exception:
                pass
        elif kind == "item_stage":
            idx = event.get("item_index")
            key = str(event.get("item_key") or "")
            label = str(event.get("item_label") or "")
            msg = event.get("message")
            if isinstance(idx, int):
                pane.expand_item(idx)
                self._active_index[task_id] = idx
                pane.set_item_stage(idx, key, label or "", str(msg or ""))
        elif kind == "item_finish":
            idx = event.get("item_index")
            ok = bool(event.get("success"))
            if isinstance(idx, int):
                pane.finish_item(idx, success=ok)
        elif kind == "total":
            total = int(event.get("total") or 0)
            self._totals[task_id] = total
            pane.set_total(total)
        elif kind == "advance":
            completed = int(event.get("completed") or 0)
            self._completeds[task_id] = completed
            pane.set_completed(completed)
            # mark finish for current active item if any
            idx = self._active_index.get(task_id)
            if idx is not None:
                pane.finish_item(idx, success=True)
                # move to next
                self._active_index[task_id] = (
                    idx + 1 if (idx + 1) < pane.item_count() else None
                )
        elif kind == "stage":
            key = str(event.get("stage_key") or "")
            label = str(event.get("stage_label") or "")
            msg = event.get("message")
            if task_id == "auto_edit" and key == "edit_group":
                title = label or (msg or "")
                idx = pane.find_index_by_title(title)
                if idx is None:
                    idx = pane.add_item(title)
                pane.expand_item(idx)
                self._active_index[task_id] = idx
            elif task_id == "auto_upload" and key == "prepare":
                title = msg or label or ""
                idx = pane.find_index_by_title(title)
                if idx is None:
                    idx = pane.add_item(title)
                pane.expand_item(idx)
                self._active_index[task_id] = idx
            else:
                # per-step updates
                idx = self._active_index.get(task_id)
                if idx is not None:
                    mapped_key = key
                    mapped_label = label
                    if task_id == "auto_upload":
                        if key == "prepare":
                            mapped_key, mapped_label = (
                                "collect",
                                "編集済動画収集",
                            )
                        elif key == "upload":
                            mapped_key, mapped_label = (
                                "upload",
                                "動画アップロード",
                            )
                    pane.set_item_stage(
                        idx, mapped_key, mapped_label or "", str(msg or "")
                    )
        elif kind == "finish":
            self._finished[task_id] = True
            try:
                if self._finished.get("auto_edit") and self._finished.get(
                    "auto_upload"
                ):
                    self.close_button.configure(state=tk.NORMAL)
                    self.cancel_button.configure(state=tk.DISABLED)
            except Exception:
                pass

    def _on_cancel(self) -> None:
        try:
            self.cancel_button.configure(
                text="キャンセル中...", state=tk.DISABLED
            )
        except Exception:
            pass
        try:
            self.controller.cancel_auto_editor_and_uploader()
        except Exception:
            pass


class TaskPane:
    """Card-styled pane with a large meter and a scrollable item list."""

    def __init__(
        self, parent: ttk.Frame, title: str, steps: List[Tuple[str, str]]
    ):
        self.parent = parent
        self.steps = steps

        # card
        self.card = CardWidget(parent, title)

        # top row: meter on left
        self.meter = Meter(
            self.card.content,
            metersize=150,
            amounttotal=100,
            amountused=0,
            amountformat="{:.0f}%",
            metertype="full",
            showtext=True,
            subtext="(0/0)",
            bootstyle="primary",  # type: ignore[arg-type]
        )
        self.meter.pack(side="left", anchor="n", padx=(0, 12), pady=(0, 6))

        # scrollable list on right
        list_container = ttk.Frame(self.card.content)
        list_container.pack(side="left", fill="both", expand=True)
        self._canvas = tk.Canvas(list_container, highlightthickness=0)
        self._vsb = ttk.Scrollbar(
            list_container, orient="vertical", command=self._canvas.yview
        )
        self._list_frame = ttk.Frame(self._canvas)
        # keep handle to the embedded window to control its width on resize
        self._list_window = self._canvas.create_window(
            (0, 0), window=self._list_frame, anchor="nw"
        )
        self._canvas.configure(yscrollcommand=self._vsb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._vsb.pack(side="right", fill="y")
        self._list_frame.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")
            ),
        )
        # make the inner frame width follow the canvas width so the right edge isn't clipped
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfigure(
                self._list_window, width=e.width
            ),
        )

        # item rows
        self._items: List[ItemRow] = []
        self._total: int = 0
        self._completed: int = 0

    # meter
    def set_total(self, total: int) -> None:
        self._total = max(0, total)
        self._update_meter()

    def set_completed(self, completed: int) -> None:
        self._completed = max(0, completed)
        self._update_meter()

    def _update_meter(self) -> None:
        percent = (
            int((self._completed / self._total) * 100)
            if self._total > 0
            else 0
        )
        self.meter.configure(amountused=max(0, min(100, percent)))
        self.meter.configure(subtext=f"({self._completed}/{self._total})")

    # items helpers
    def find_index_by_title(self, title: str) -> int | None:
        for i, row in enumerate(self._items):
            if row.title == title and not row.is_finished():
                return i
        return None

    # items
    def add_item(self, title: str) -> int:
        row = ItemRow(self._list_frame, title=title, steps=self.steps)
        row.frame.pack(fill="x", padx=(0, 4), pady=4)
        self._items.append(row)
        # Collapse by default: only the active item should be expanded
        row.collapse()
        return len(self._items) - 1

    def item_count(self) -> int:
        return len(self._items)

    def expand_item(self, index: int) -> None:
        if 0 <= index < len(self._items):
            # Collapse others to ensure only one expanded at a time
            for i, item in enumerate(self._items):
                if i == index:
                    continue
                item.collapse()
            self._items[index].expand()

    def set_item_stage(
        self, index: int, key: str, label: str, message: Optional[str]
    ) -> None:
        if 0 <= index < len(self._items):
            self._items[index].set_stage(key, label, message or "")

    def finish_item(self, index: int, success: bool) -> None:
        if 0 <= index < len(self._items):
            self._items[index].finish(success)


class ItemRow:
    """Single item row with header (title + progress bar) and collapsible checklist."""

    def __init__(
        self, parent: ttk.Frame, title: str, steps: List[Tuple[str, str]]
    ):
        self.parent = parent
        self.title = title
        self.steps = steps

        colors = cast(ttk.Colors, ttk.Style().colors)
        self._color_pending = colors.secondary
        self._color_active = colors.primary
        self._color_success = colors.success
        self._color_fail = colors.danger

        self.frame = ttk.Frame(parent)
        self.header = ttk.Frame(self.frame)
        self.header.pack(fill="x")

        try:
            self.title_label = ttk.Floodgauge(self.header, text=title)
            self.title_label.pack(side="left", fill="x", expand=True)

        except Exception as e:
            print(f"Error creating title label: {e}")

        # checklist
        self.body = ttk.Frame(self.frame)
        self.body.pack(fill="x", pady=(6, 2))
        self._labels: Dict[str, ttk.Label] = {}
        self._message_labels: Dict[str, ttk.Label] = {}

        # derive a slightly smaller font for messages
        base_font = tkfont.nametofont("TkDefaultFont")
        try:
            base_size = int(base_font.cget("size"))
        except Exception:
            base_size = 10
        self._msg_font: tkfont.Font = tkfont.Font(size=max(8, base_size - 1))

        for key, label in self.steps:
            row = ttk.Frame(self.body)
            row.pack(fill="x", pady=(2, 2))

            lbl = ttk.Label(row, text=f"☐{label}", anchor="w")
            self._set_label_color(lbl, self._color_pending)
            lbl.pack(side="left", fill="x", expand=True)
            self._labels[key] = lbl

            msg_lbl = ttk.Label(row, text="", anchor="w")
            try:
                msg_lbl.configure(font=self._msg_font)
            except Exception:
                pass
            self._set_label_color(msg_lbl, self._color_pending)
            msg_lbl.pack(side="left", fill="x", padx=(10, 0))
            self._message_labels[key] = msg_lbl

        self._active_key: Optional[str] = None
        self._done: set[str] = set()
        self._expanded: bool = True
        self._update_progress()

    def is_finished(self) -> bool:
        return len(self._done) >= len(self.steps)

    def _update_progress(self) -> None:
        total = len(self.steps)
        done = len(self._done)
        percent = int((done / total) * 100) if total > 0 else 0
        self.title_label.configure(value=percent)

    def set_stage(self, key: str, label: str, message: str) -> None:
        # mark previous as done
        prev_key = self._active_key
        if prev_key and prev_key in self._labels:
            prev_lbl = self._labels[prev_key]
            prev_text = (
                prev_lbl.cget("text").replace("▷", "☐").replace("✖", "☐")
            )
            prev_lbl.configure(text=prev_text.replace("☐", "✔", 1))
            self._set_label_color(prev_lbl, self._color_success)
            self._done.add(prev_key)

        self._active_key = key
        # ensure label exists
        if key not in self._labels:
            # append unknown step to bottom if necessary (label + right side message)
            row = ttk.Frame(self.body)
            row.pack(fill="x", pady=(2, 2))

            lbl = ttk.Label(row, text=f"☐{label}", anchor="w")
            self._set_label_color(lbl, self._color_pending)
            lbl.pack(side="left", fill="x", expand=True)
            self._labels[key] = lbl

            msg_lbl = ttk.Label(row, text="", anchor="w")
            try:
                msg_lbl.configure(font=self._msg_font)
            except Exception:
                pass
            self._set_label_color(msg_lbl, self._color_pending)
            msg_lbl.pack(side="left", fill="x", padx=(10, 0))
            self._message_labels[key] = msg_lbl

        cur_lbl = self._labels[key]
        cur_lbl.configure(text=f"▷ {label}")
        self._set_label_color(cur_lbl, self._color_active)
        # update message display (smaller, secondary color)
        if prev_key and prev_key in self._message_labels:
            try:
                # clear previous active message
                self._message_labels[prev_key].configure(text="")
            except Exception:
                pass
        msg_lbl = self._message_labels.get(key)
        if msg_lbl is not None:
            msg_lbl.configure(text=str(message))
            self._set_label_color(msg_lbl, self._color_pending)
        self._update_progress()

    def finish(self, success: bool) -> None:
        # mark current active
        if self._active_key and self._active_key in self._labels:
            lbl = self._labels[self._active_key]
            if success:
                lbl.configure(text=lbl.cget("text").replace("▷", "✔", 1))
                self._set_label_color(lbl, self._color_success)
                self._done.add(self._active_key)
            else:
                lbl.configure(text=lbl.cget("text").replace("▷", "✖", 1))
                self._set_label_color(lbl, self._color_fail)
        # mark remaining as done on success
        if success:
            for key, lbl in self._labels.items():
                if key not in self._done:
                    lbl.configure(text=lbl.cget("text").replace("☐", "✔", 1))
                    self._set_label_color(lbl, self._color_success)
            self._done = set(self._labels.keys())

        self._update_progress()
        self.collapse()

    def expand(self) -> None:
        if not self._expanded:
            self.body.pack(fill="x", pady=(6, 2))
            self._expanded = True

    def collapse(self) -> None:
        if self._expanded:
            self.body.forget()
            self._expanded = False

    # utils
    def _set_label_color(self, lbl: ttk.Label, color: str) -> None:
        try:
            lbl.configure(foreground=color)
        except Exception:
            pass
