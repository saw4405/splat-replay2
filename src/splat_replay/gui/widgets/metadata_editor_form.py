"""メタデータ編集ウィジェット.

AutoRecorder の状態をリアルタイム表示し、メタデータを編集する。
"""

from __future__ import annotations

import datetime
import re
from typing import Dict, Optional, cast

import dateparser
import ttkbootstrap as ttk

from splat_replay.domain.models import GameMode, Match, Rule, Stage
from splat_replay.shared.logger import get_logger


class MetadataEditorForm:
    """メタデータ編集ウィジェット（AutoRecorder の状態をリアルタイム表示）"""

    def __init__(
        self,
        parent: ttk.Frame,
        metadata: Optional[Dict[str, str | None]] = None,
    ) -> None:
        self.logger = get_logger()
        self.parent = parent

        self.colors: ttk.Colors = ttk.Style().colors  # type: ignore
        self.fields: dict[str, ttk.Combobox | ttk.Spinbox | ttk.Entry] = {}
        self.manual_overrides: dict[str, str | int] = {}
        self._fields_config = {
            "game_mode": ("ゲームモード", "select"),
            "started_at": ("マッチング開始", "datetime"),
            "match": ("マッチタイプ", "select"),
            "rule": ("ルール", "select"),
            "rate": ("レート", "text"),
            "judgement": ("判定", "select"),
            "stage": ("ステージ", "select"),
            "kill": ("キル数", "number"),
            "death": ("デス数", "number"),
            "special": ("スペシャル使用回数", "number"),
        }
        self._last_valid_values: Dict[str, str] = {}
        self._time_full_iso_re = re.compile(
            r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$"
        )
        self._create_fields()
        self.update(metadata)
        self.logger.info("MetadataEditorWidget が初期化されました")

    def _create_fields(self) -> None:
        self.form = ttk.Frame(self.parent)
        self.form.pack(fill="both", expand=True)

        # 選択肢定義
        self.field_choices = {
            "game_mode": [m.value for m in GameMode],
            "match": [m.value for m in Match],
            "rule": [r.value for r in Rule],
            "stage": [s.value for s in Stage],
            "judgement": ["未判定", "WIN", "LOSE"],
        }

        for i, (field_name, (label_text, field_type)) in enumerate(
            self._fields_config.items()
        ):
            self._setup_form_item(i, field_name, label_text, field_type)

    def _setup_form_item(
        self, row: int, field_name: str, label_text: str, field_type: str
    ) -> None:
        label = ttk.Label(
            self.form,
            text=f"{label_text}",
        )
        label.grid(row=row, column=0, sticky="w", padx=(0, 20), pady=2)

        if field_type == "select":
            values = self.field_choices.get(field_name, [])
            combobox = ttk.Combobox(
                self.form,
                values=values,
            )
            combobox.bind(
                "<<ComboboxSelected>>",
                lambda e, fn=field_name, w=combobox: self._on_manual_edit(
                    fn, w.get()
                ),
            )
            combobox.grid(row=row, column=1, sticky="ew", pady=2)
            self.fields[field_name] = combobox

        elif field_type == "number":
            var = ttk.StringVar()
            spinbox = ttk.Spinbox(
                self.form,
                from_=0,
                to=999,
                width=25,
                textvariable=var,
                command=lambda fn=field_name, v=var: self._on_manual_edit(
                    fn, v.get()
                ),
                wrap=True,
            )
            spinbox.bind(
                "<FocusOut>",
                lambda e, fn=field_name, v=var: self._on_manual_edit(
                    fn, v.get()
                ),
            )
            spinbox.bind(
                "<Return>",
                lambda e, fn=field_name, v=var: self._on_manual_edit(
                    fn, v.get()
                ),
            )
            spinbox.grid(row=row, column=1, sticky="ew", pady=2)
            self.fields[field_name] = spinbox

        elif field_type == "datetime":
            frame = ttk.Frame(self.form)
            entry = ttk.Entry(frame)
            button = ttk.Button(
                frame,
                text="Now",
                width=4,
                bootstyle="secondary",  # type:ignore
                command=lambda fn=field_name, w=entry: self._set_now(fn, w),
            )
            entry.pack(side="left", fill="both", expand=True, padx=(0, 4))
            button.pack(side="left")
            entry.bind(
                "<FocusOut>",
                lambda e, fn=field_name, w=entry: self._on_manual_edit(
                    fn, w.get()
                ),
            )
            entry.bind(
                "<Return>",
                lambda e, fn=field_name, w=entry: self._on_manual_edit(
                    fn, w.get()
                ),
            )
            frame.grid(row=row, column=1, sticky="ew", pady=2)
            self.fields[field_name] = entry

        elif field_type == "text":
            entry = ttk.Entry(
                self.form,
                width=25,
            )
            entry.bind(
                "<FocusOut>",
                lambda e, fn=field_name, w=entry: self._on_manual_edit(
                    fn, w.get()
                ),
            )
            entry.bind(
                "<Return>",
                lambda e, fn=field_name, w=entry: self._on_manual_edit(
                    fn, w.get()
                ),
            )
            entry.grid(row=row, column=1, sticky="ew", pady=2)
            self.fields[field_name] = entry

        else:
            raise ValueError(f"Unknown field type: {field_type}")

    def is_edited(self) -> bool:
        return bool(self.manual_overrides)

    def reset(self) -> None:
        self.manual_overrides.clear()

        # 色を戻す
        for _, field in self.fields.items():
            field.configure(foreground=self.colors.fg)

        self.update(None)
        self.logger.info("metadata_manual_overrides_reset")

    def update(self, metadata: Optional[Dict[str, str | None]]) -> None:
        try:
            game_mode_str = (metadata or {}).get("game_mode") or "未取得"
            self._update_field("game_mode", game_mode_str)

            started_str = (metadata or {}).get("started_at") or "未開始"
            self._update_field("started_at", started_str)

            match_str = (metadata or {}).get("match") or "未取得"
            self._update_field("match", match_str)

            rule_str = (metadata or {}).get("rule") or "未取得"
            self._update_field("rule", rule_str)

            rate_str = (metadata or {}).get("rate") or "未検出"
            self._update_field("rate", rate_str)

            judgement_str = (metadata or {}).get("judgement") or "未判定"
            self._update_field("judgement", judgement_str)

            stage_str = (metadata or {}).get("stage") or "未取得"
            self._update_field("stage", stage_str)

            kill_str = (metadata or {}).get("kill") or "未取得"
            self._update_field("kill", kill_str)

            death_str = (metadata or {}).get("death") or "未取得"
            self._update_field("death", death_str)

            special_str = (metadata or {}).get("special") or "未取得"
            self._update_field("special", special_str)

        except Exception as e:
            self.logger.error(f"メタデータ更新でエラー: {e}")
            for field_name in self.fields:
                self._update_field(field_name, "エラー")

    def _update_field(self, field_name: str, value: str) -> None:
        # 手動上書きが存在する場合は自動更新しない
        if field_name in self.manual_overrides:
            return
        if field_name not in self.fields:
            return

        field = self.fields[field_name]
        text_value = str(value)
        try:
            if isinstance(field, ttk.Combobox):
                values = list(cast(tuple[str, ...], field.cget("values")))
                if text_value not in values and text_value not in (
                    "",
                    "未取得",
                ):
                    raise ValueError(
                        f"Unknown value for {field_name}: {text_value}"
                    )
                field.set(text_value)

            elif isinstance(field, ttk.Spinbox):
                field.delete(0, ttk.END)
                field.insert(0, text_value)

            elif isinstance(field, ttk.Entry):
                field.delete(0, ttk.END)
                field.insert(0, text_value)

                # started_at など datetime 型で妥当な時刻なら記録
                field_config = self._fields_config.get(field_name)
                if not field_config:
                    raise ValueError(f"Unknown field config for {field_name}")
                field_type = field_config[1]
                if field_type == "datetime":
                    try:
                        datetime.datetime.fromisoformat(text_value)
                        self._last_valid_values[field_name] = text_value
                    except ValueError:
                        pass
        except Exception:
            pass

    def _on_manual_edit(self, field_name: str, raw_value: str | int) -> None:
        _, field_type = self._fields_config.get(field_name, (None, None))
        if not field_type:
            raise ValueError(f"Unknown field type for {field_name}")
        field = self.fields.get(field_name)
        if not field:
            raise ValueError(f"Unknown widget for {field_name}")

        value: str | int = raw_value
        if field_type == "number":
            try:
                value = int(raw_value)
            except Exception:
                return

        elif field_type == "datetime":
            assert isinstance(raw_value, str)
            if isinstance(raw_value, str):
                raw_s = raw_value.strip()
                if raw_s in ("", "未開始"):
                    return
                try:
                    # parsed = datetime.datetime.fromisoformat(raw_s)
                    parsed = dateparser.parse(
                        raw_s,
                        settings={
                            "PREFER_DATES_FROM": "future",
                            "DATE_ORDER": "YMD",
                            "STRICT_PARSING": False,
                        },
                    )
                    if not parsed:
                        raise ValueError(f"Invalid datetime format: {raw_s}")

                    value = parsed.strftime("%Y-%m-%d %H:%M:%S")
                    field.delete(0, ttk.END)
                    field.insert(0, value)
                    self._last_valid_values[field_name] = value
                except Exception:
                    # 失敗 -> 前回値復元
                    prev = self._last_valid_values.get(field_name, "")
                    field.delete(0, ttk.END)
                    if prev:
                        field.insert(0, prev)
                    self.logger.warning(
                        "invalid_time_input", field=field_name, value=raw_value
                    )
                    return

        self.manual_overrides[field_name] = value

        # 手動編集は強調色
        field.configure(foreground=self.colors.primary)

        self.logger.info(
            "metadata_manual_override", field=field_name, value=str(value)
        )

    def _set_now(self, field_name: str, entry: ttk.Entry) -> None:
        # ISO 形式 (日付含む) に切り替え
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry.delete(0, ttk.END)
        entry.insert(0, now_str)
        self._on_manual_edit(field_name, now_str)

    def get_metadata(self) -> Dict[str, str]:
        return {
            field_name: field.get()
            for field_name, field in self.fields.items()
        }
