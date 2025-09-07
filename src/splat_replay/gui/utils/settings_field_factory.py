"""設定フィールド生成ユーティリティ (型安全版)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, simpledialog
from typing import List, Optional, Tuple, Union, cast

import ttkbootstrap as ttk
from pydantic import SecretStr

from splat_replay.gui.controllers.settings_controller import SettingItemType


class ExtendedFrame(ttk.Frame):
    """内部に Entry や Listbox を保持するための拡張フレーム."""

    _entry: tk.Entry | None
    _listbox: tk.Listbox | None

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401
        super().__init__(*args, **kwargs)
        self._entry = None
        self._listbox = None


FieldWidgetReturn = Union[
    tk.Widget, Tuple[tk.Widget, tk.BooleanVar], ExtendedFrame
]


class SettingsFieldFactory:
    """フィールド種別に応じて適切なウィジェットを生成."""

    @staticmethod
    def create_field(
        parent: tk.Widget,
        field_id: str,
        field_type: str,
        field_choices: Optional[List[str]],
        field_value: SettingItemType,
        field_recommended: bool,
    ) -> FieldWidgetReturn:
        bootstyle = "primary" if field_recommended else "secondary"

        if field_type == "path":
            if not isinstance(field_value, Path):
                raise ValueError("Invalid field value for 'path'")
            return SettingsFieldFactory._create_path_field(
                parent, field_id, field_value, bootstyle
            )
        if field_type == "integer":
            if not isinstance(field_value, int):
                raise ValueError("Invalid field value for 'integer'")
            return SettingsFieldFactory._create_integer_field(
                parent, field_value, bootstyle
            )
        if field_type == "float":
            if not isinstance(field_value, float):
                raise ValueError("Invalid field value for 'float'")
            return SettingsFieldFactory._create_float_field(
                parent, field_value, bootstyle
            )
        if field_type == "password":
            if not isinstance(field_value, SecretStr):
                raise ValueError("Invalid field value for 'password'")
            return SettingsFieldFactory._create_password_field(
                parent, field_value, bootstyle
            )
        if field_type == "boolean":
            if not isinstance(field_value, bool):
                raise ValueError("Invalid field value for 'boolean'")
            return SettingsFieldFactory._create_boolean_field(
                parent, field_value, bootstyle
            )
        if field_type == "select":
            if not isinstance(field_value, str) or not field_choices:
                raise ValueError("Invalid field value for 'select'")
            return SettingsFieldFactory._create_select_field(
                parent, field_choices, field_value, bootstyle
            )
        if field_type == "list":
            if not isinstance(field_value, list):
                raise ValueError("Invalid field value for 'list'")
            return SettingsFieldFactory._create_list_field(
                parent, field_value, bootstyle
            )
        if field_type == "template":
            if not isinstance(field_value, str):
                raise ValueError("Invalid field value for 'template'")
            return SettingsFieldFactory._create_template_field(
                parent, field_value, bootstyle
            )
        elif field_type == "text":
            if not isinstance(field_value, str):
                raise ValueError("Invalid field value for 'text'")
            return SettingsFieldFactory._create_text_field(
                parent, field_value, bootstyle
            )
        raise ValueError(f"Unknown field type: {field_type}")

    # ---- creators -------------------------------------------------
    @staticmethod
    def _create_text_field(
        parent: tk.Widget,
        value: str,
        bootstyle: str,
    ) -> tk.Widget:
        entry = ttk.Entry(parent, width=40, bootstyle=bootstyle)  # type:ignore
        entry.insert(0, str(value))
        return entry

    @staticmethod
    def _create_integer_field(
        parent: tk.Widget,
        value: int,
        bootstyle: str,
    ) -> tk.Widget:
        spin = ttk.Spinbox(
            parent,
            from_=0,
            to=99999,
            width=40,
            bootstyle=bootstyle,  # type:ignore
        )
        spin.delete(0, tk.END)
        spin.insert(0, str(value))
        return spin

    @staticmethod
    def _create_float_field(
        parent: tk.Widget,
        value: float,
        bootstyle: str,
    ) -> tk.Widget:
        spin = ttk.Spinbox(
            parent,
            from_=0.0,
            to=99999.0,
            width=40,
            bootstyle=bootstyle,  # type:ignore
            increment=0.1,
        )
        spin.delete(0, tk.END)
        spin.insert(0, str(value))
        return spin

    @staticmethod
    def _create_password_field(
        parent: tk.Widget,
        value: SecretStr,
        bootstyle: str,
    ) -> tk.Widget:
        entry = ttk.Entry(parent, show="*", width=40, bootstyle=bootstyle)  # type:ignore
        entry.insert(0, value.get_secret_value())
        return entry

    @staticmethod
    def _create_path_field(
        parent: tk.Widget,
        field_name: str,
        value: Path,
        bootstyle: str,
    ) -> ExtendedFrame:
        frame = ExtendedFrame(parent)
        entry = ttk.Entry(
            frame,
            width=35,
            bootstyle=bootstyle,  # type:ignore
        )
        entry.insert(0, str(value))
        entry.pack(side="left", fill="x", expand=True)

        def browse() -> None:
            name_lower = field_name.lower()
            chosen: Optional[str]
            if (
                "dir" in name_lower
                or "directory" in name_lower
                or "folder" in name_lower
            ):
                chosen = filedialog.askdirectory(title=f"Select {field_name}")
            else:
                chosen = filedialog.askopenfilename(
                    title=f"Select {field_name}"
                )
            if chosen:
                entry.delete(0, tk.END)
                entry.insert(0, chosen)

        ttk.Button(
            frame,
            text="参照",
            command=browse,
            width=5,
            bootstyle="secondary",  # type:ignore
        ).pack(side="right", padx=(5, 0))
        frame._entry = entry
        return frame

    @staticmethod
    def _create_boolean_field(
        parent: tk.Widget,
        value: bool,
        bootstyle: str,
    ) -> Tuple[tk.Widget, tk.BooleanVar]:
        var = tk.BooleanVar(value=bool(value))
        widget = ttk.Checkbutton(
            parent,
            variable=var,
            bootstyle=f"{bootstyle}-round-toggle",  # type:ignore
        )
        return widget, var

    @staticmethod
    def _create_select_field(
        parent: tk.Widget,
        choices: List[str],
        value: str,
        bootstyle: str,
    ) -> tk.Widget:
        combo = ttk.Combobox(
            parent,
            values=choices,
            width=37,
            bootstyle=bootstyle,  # type:ignore
        )
        combo.set(value)
        return combo

    @staticmethod
    def _create_list_field(
        parent: tk.Widget,
        value: List[str],
        bootstyle: str,
    ) -> ExtendedFrame:
        colors = cast(ttk.Colors, ttk.Style().colors)

        frame = ExtendedFrame(parent)
        listbox = tk.Listbox(
            frame,
            height=4,
            width=35,
            bg=colors.bg,
            fg=colors.fg,
            highlightthickness=1,
            borderwidth=0,
            relief="flat",
        )
        if isinstance(value, list):
            for item in value:
                listbox.insert(tk.END, str(item))
        listbox.pack(side="left", fill="both", expand=True)

        btns = ttk.Frame(frame)
        btns.pack(side="right", fill="y", padx=(5, 0))

        def add_item() -> None:
            new = simpledialog.askstring(
                "項目追加", "追加する項目を入力してください:"
            )
            if new:
                listbox.insert(tk.END, new)

        def edit_item() -> None:
            sel = listbox.curselection()
            if sel:
                cur = listbox.get(sel[0])
                new_val = simpledialog.askstring(
                    "項目編集", "項目を編集してください:", initialvalue=cur
                )
                if new_val is not None:
                    listbox.delete(sel[0])
                    listbox.insert(sel[0], new_val)

        def remove_item() -> None:
            sel = listbox.curselection()
            if sel:
                listbox.delete(sel[0])

        ttk.Button(
            btns,
            text="追加",
            command=add_item,
            width=5,
            bootstyle="secondary",  # type:ignore
        ).pack(pady=(0, 5))
        ttk.Button(
            btns,
            text="編集",
            command=edit_item,
            width=5,
            bootstyle="secondary",  # type:ignore
        ).pack(pady=(0, 5))
        ttk.Button(
            btns,
            text="削除",
            command=remove_item,
            width=5,
            bootstyle="secondary",  # type:ignore
        ).pack()
        frame._listbox = listbox
        return frame

    @staticmethod
    def _create_template_field(
        parent: tk.Widget,
        value: str,
        bootstyle: str,
    ) -> tk.Text:
        text = ttk.Text(
            parent,
            height=10,
            width=40,
            wrap=tk.WORD,
            highlightthickness=1,
            borderwidth=0,
            relief="flat",
            bootstyle=bootstyle,  # type:ignore
        )
        text.insert("1.0", str(value))
        return text

    # ---- helpers -------------------------------------------------

    @staticmethod
    def get_widget_value(widget: FieldWidgetReturn) -> SettingItemType:
        if isinstance(widget, tk.Entry):
            return widget.get()
        if isinstance(widget, tk.Spinbox):
            txt = widget.get()
            if txt.isdigit():
                return int(txt)
            try:
                return float(txt)
            except ValueError:
                return txt
        if isinstance(widget, tk.Text):
            return widget.get("1.0", tk.END).strip()
        if isinstance(widget, ttk.Combobox):
            return widget.get()
        if isinstance(widget, ExtendedFrame):
            if widget._entry is not None:
                return widget._entry.get()
            if widget._listbox is not None:
                return list(widget._listbox.get(0, tk.END))
        if isinstance(widget, tuple) and len(widget) == 2:
            _w, var = widget
            return var.get()
        raise ValueError(f"Unknown widget type: {type(widget)}")

    @staticmethod
    def validate_field_value(
        field_name: str,
        value: SettingItemType,
        field_type: str,
    ) -> Tuple[bool, str]:
        if field_type == "number":
            val_str = str(value)
            try:
                num = float(val_str) if "." in val_str else int(val_str)
            except ValueError:
                return False, "数値を入力してください"
            lname = field_name.lower()
            if "port" in lname and not (1 <= num <= 65535):
                return False, "ポート番号は1-65535の範囲で入力してください"
            if "timeout" in lname and num < 0:
                return False, "タイムアウト値は0以上である必要があります"
            if "fps" in lname and not (1 <= num <= 120):
                return False, "FPS は1-120の範囲で入力してください"
            return True, ""
        if field_type == "path":
            if value and isinstance(value, str) and not Path(value).exists():
                return False, f"指定されたパスが存在しません: {value}"
            return True, ""
        if field_type == "password":
            if not value:
                return False, "パスワードを入力してください"
            return True, ""
        return True, ""
