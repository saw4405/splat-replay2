"""字幕編集ダイアログ."""

from __future__ import annotations

import re
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Dialog, Messagebox
from ttkbootstrap.tableview import Tableview

from splat_replay.shared.logger import get_logger


@dataclass
class SubtitleRow:
    """字幕行の情報を保持するデータクラス."""

    start: float
    end: float
    text: str


_TIME_PATTERN = re.compile(
    r"^(?P<h>\d{1,3}):(?P<m>[0-5]\d):(?P<s>[0-5]\d),(?P<ms>\d{3})$"
)


class SubtitleEditorDialog(Dialog):
    """字幕を表形式で編集するダイアログ."""

    _DEFAULT_DURATION = 2.5

    def __init__(
        self,
        window: ttk.Window,
        video_path: Path,
        subtitle: str | None,
    ) -> None:
        super().__init__(
            window,
            title=f"字幕編集: {video_path.name}",
        )
        self.logger = get_logger()
        self.window = window
        self.video_path = video_path
        self._initial_subtitle = subtitle or ""
        self._closed = False
        self.rows: list[SubtitleRow] = self._parse_srt(self._initial_subtitle)
        self.table: Tableview | None = None
        self.start_var = tk.StringVar(value="")
        self.end_var = tk.StringVar(value="")
        self.start_entry: ttk.Entry | None = None
        self.end_entry: ttk.Entry | None = None
        self.text_input: tk.Text | None = None
        self.apply_button: ttk.Button | None = None
        self.delete_button: ttk.Button | None = None

        self.logger.info(
            "字幕編集ダイアログが初期化されました", video=str(video_path)
        )

    def create_body(self, master: tk.Widget):
        container = ttk.Frame(master, padding=10)
        container.pack(fill="both", expand=True)

        info_label = ttk.Label(
            container,
            text=(
                "表の各行に開始・終了時刻と本文を入力してください。\n"
                "番号は自動採番され、保存時に時間が整列します。"
            ),
            anchor="w",
            justify="left",
        )
        info_label.pack(fill="x", pady=(0, 8))

        table_frame = ttk.Frame(container)
        table_frame.pack(fill="both", expand=True)

        coldata = [
            {"text": "No.", "width": 60, "stretch": False},
            {"text": "開始", "width": 150, "stretch": False},
            {"text": "終了", "width": 150, "stretch": False},
            {"text": "本文 (改行可)", "width": 400, "stretch": True},
        ]
        self.table = Tableview(
            table_frame,
            coldata=coldata,
            paginated=False,
            searchable=False,
            bootstyle="dark",
            height=10,
        )
        self.table.pack(fill="both", expand=True)
        self.table.view.bind("<<TreeviewSelect>>", self._on_row_selected)

        button_frame = ttk.Frame(container)
        button_frame.pack(fill="x", pady=(8, 4))

        add_button = ttk.Button(
            button_frame,
            text="＋ 行を追加",
            command=self._add_row,
            bootstyle="success-outline",  # type: ignore[arg-type]
        )
        add_button.pack(side="left", padx=(0, 8))

        self.delete_button = ttk.Button(
            button_frame,
            text="－ 行を削除",
            command=self._delete_row,
            state="disabled",
            bootstyle="danger-outline",  # type: ignore[arg-type]
        )
        self.delete_button.pack(side="left", padx=(0, 8))

        normalize_button = ttk.Button(
            button_frame,
            text="⏱ 時間を調整",
            command=self._on_normalize,
            bootstyle="info-outline",  # type: ignore[arg-type]
        )
        normalize_button.pack(side="right")

        time_frame = ttk.Frame(container)
        time_frame.pack(fill="x", pady=(4, 4))

        ttk.Label(time_frame, text="開始 (hh:mm:ss,mmm)").grid(
            row=0, column=0, sticky="w"
        )
        self.start_entry = ttk.Entry(
            time_frame, textvariable=self.start_var, width=20
        )
        self.start_entry.grid(row=0, column=1, sticky="w", padx=(4, 16))

        ttk.Label(time_frame, text="終了 (hh:mm:ss,mmm)").grid(
            row=0, column=2, sticky="w"
        )
        self.end_entry = ttk.Entry(
            time_frame, textvariable=self.end_var, width=20
        )
        self.end_entry.grid(row=0, column=3, sticky="w", padx=(4, 0))

        text_label = ttk.Label(container, text="本文")
        text_label.pack(anchor="w")

        self.text_input = tk.Text(container, height=6, wrap="word")
        self.text_input.pack(fill="both", expand=True)

        apply_frame = ttk.Frame(container)
        apply_frame.pack(fill="x", pady=(6, 0))
        self.apply_button = ttk.Button(
            apply_frame,
            text="選択行に反映",
            command=self._apply_changes,
            bootstyle="primary-outline",  # type: ignore[arg-type]
            state="disabled",
        )
        self.apply_button.pack(side="right")

        self._refresh_table(select_index=0 if self.rows else None)
        if not self.rows:
            self._set_form_enabled(False)

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
        self._normalize_rows()
        srt = self._rows_to_srt()
        self._result = srt
        self.close()

    def _on_close(self) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return

        if not self._toplevel:
            raise RuntimeError("Dialog is not initialized")

        self._toplevel.after_idle(self._toplevel.destroy)
        self._closed = True

    def _on_row_selected(self, _event: tk.Event | None) -> None:
        index = self._get_selected_index()
        if index is None:
            self._set_form_enabled(False)
            return

        if not self.delete_button:
            return

        self.delete_button.config(state="normal")
        self._set_form_enabled(True)
        row = self.rows[index]
        self.start_var.set(self._format_time(row.start))
        self.end_var.set(self._format_time(row.end))
        if self.text_input:
            self.text_input.config(state="normal")
            self.text_input.delete("1.0", "end")
            self.text_input.insert("1.0", row.text)

    def _add_row(self) -> None:
        if self.table is None:
            return

        if self.rows:
            last_end = max(row.end for row in self.rows)
            start = last_end
        else:
            start = 0.0
        new_row = SubtitleRow(
            start=start, end=start + self._DEFAULT_DURATION, text=""
        )
        self.rows.append(new_row)
        self._normalize_rows()
        new_index = self.rows.index(new_row)
        self._refresh_table(select_index=new_index)
        self._set_form_enabled(True)

    def _delete_row(self) -> None:
        index = self._get_selected_index()
        if index is None:
            return
        self.rows.pop(index)
        self._refresh_table(
            select_index=min(index, len(self.rows) - 1) if self.rows else None
        )
        if not self.rows:
            self._set_form_enabled(False)
            if self.delete_button:
                self.delete_button.config(state="disabled")

    def _apply_changes(self) -> None:
        index = self._get_selected_index()
        if index is None:
            return

        start_value = self.start_var.get().strip()
        end_value = self.end_var.get().strip()

        start = self._parse_time(start_value)
        if start is None:
            Messagebox.ok(
                "時刻の形式が不正です",
                "開始時刻は hh:mm:ss,mmm で入力してください。",
            )
            return

        end = self._parse_time(end_value)
        if end is None:
            Messagebox.ok(
                "時刻の形式が不正です",
                "終了時刻は hh:mm:ss,mmm で入力してください。",
            )
            return

        if end <= start:
            Messagebox.ok(
                "時刻の整合性",
                "終了時刻は開始時刻より後になるように入力してください。",
            )
            return

        text = ""
        if self.text_input:
            text = self.text_input.get("1.0", "end-1c")

        target = self.rows[index]
        target.start = max(0.0, start)
        target.end = max(target.start + 0.001, end)
        target.text = text

        self._normalize_rows()
        new_index = self.rows.index(target)
        self._refresh_table(select_index=new_index)

    def _on_normalize(self) -> None:
        self._normalize_rows()
        self._refresh_table(select_index=self._get_selected_index())

    def _refresh_table(self, select_index: int | None) -> None:
        if not self.table:
            return

        self.table.delete_rows()
        if not self.rows:
            return

        self._normalize_rows()
        row_data: list[tuple[str, str, str, str]] = []
        for idx, row in enumerate(self.rows, start=1):
            row_data.append(
                (
                    str(idx),
                    self._format_time(row.start),
                    self._format_time(row.end),
                    row.text.replace("\n", "\\n"),
                )
            )

        self.table.insert_rows("end", row_data)

        if select_index is not None and 0 <= select_index < len(self.rows):
            item = self.table.view.get_children()[select_index]
            self.table.view.selection_set(item)
            self.table.view.focus(item)
            self._on_row_selected(None)
        else:
            self.table.view.selection_remove(self.table.view.selection())
            if self.delete_button:
                self.delete_button.config(state="disabled")

    def _set_form_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        if self.start_entry is not None:
            self.start_entry.config(state=state)
        if self.end_entry is not None:
            self.end_entry.config(state=state)
        if self.text_input is not None:
            self.text_input.config(state=state)
            if not enabled:
                self.text_input.delete("1.0", "end")
        if self.apply_button is not None:
            self.apply_button.config(state="normal" if enabled else "disabled")
        if not enabled:
            self.start_var.set("")
            self.end_var.set("")

    def _get_selected_index(self) -> int | None:
        if not self.table:
            return None
        selection = self.table.view.selection()
        if not selection:
            return None
        item = selection[0]
        return self.table.view.index(item)

    def _normalize_rows(self) -> None:
        if not self.rows:
            return

        self.rows.sort(key=lambda r: r.start)
        previous_end = 0.0
        for row in self.rows:
            row.start = max(row.start, previous_end)
            if row.end <= row.start:
                row.end = row.start + self._DEFAULT_DURATION
            previous_end = row.end

    def _rows_to_srt(self) -> str:
        if not self.rows:
            return ""

        lines: list[str] = []
        for idx, row in enumerate(self.rows, start=1):
            lines.append(str(idx))
            lines.append(
                f"{self._format_time(row.start)} --> {self._format_time(row.end)}"
            )
            lines.append(row.text)
            lines.append("")
        result = "\n".join(lines).strip()
        return result + "\n" if result else ""

    def _parse_srt(self, subtitle: str) -> list[SubtitleRow]:
        rows: list[SubtitleRow] = []
        if not subtitle.strip():
            return rows

        blocks = re.split(r"\n\s*\n", subtitle.strip())
        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) < 2:
                continue
            has_index_line = lines[0].strip().isdigit()
            timing_line = lines[1] if has_index_line else lines[0]
            text_lines = lines[2:] if has_index_line else lines[1:]
            start, end = self._parse_timing_line(timing_line)
            if start is None or end is None:
                continue
            rows.append(
                SubtitleRow(start=start, end=end, text="\n".join(text_lines))
            )
        rows.sort(key=lambda r: r.start)
        return rows

    def _parse_timing_line(
        self, line: str
    ) -> tuple[float | None, float | None]:
        parts = line.split("-->")
        if len(parts) != 2:
            return (None, None)
        start = self._parse_time(parts[0].strip())
        end = self._parse_time(parts[1].strip())
        return (start, end)

    def _parse_time(self, value: str) -> float | None:
        match = _TIME_PATTERN.match(value)
        if not match:
            return None
        hours = int(match.group("h"))
        minutes = int(match.group("m"))
        seconds = int(match.group("s"))
        milliseconds = int(match.group("ms"))
        total = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
        return total

    def _format_time(self, value: float) -> str:
        seconds = max(0.0, value)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis >= 1000:
            millis -= 1000
            secs += 1
        if secs >= 60:
            secs -= 60
            minutes += 1
        if minutes >= 60:
            minutes -= 60
            hours += 1
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
