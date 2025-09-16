"""メインウィンドウ: Splat Replay GUI のメイン録画画面

循環インポート (main_app <-> main_window) 回避のため、`SplatReplayGUI` は
型チェック時のみインポートし、実行時には前方参照 (PEP 563 / __future__ annotations)
で解決する。
"""

from __future__ import annotations

from pathlib import Path
from tkinter import font
from typing import Callable, Dict, Optional

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.style import ThemeDefinition
from ttkbootstrap.utility import enable_high_dpi_awareness

from splat_replay.domain.services import RecordState
from splat_replay.gui.dialogs.metadata_editor_dialog import (
    MetadataEditorDialog,
)
from splat_replay.gui.dialogs.progress_dialog import ProgressDialog
from splat_replay.gui.dialogs.settings_dialog import SettingsDialog
from splat_replay.gui.utils.application_controller import (
    GUIApplicationController,
)
from splat_replay.gui.widgets.metadata_editor_card import MetadataEditorCard
from splat_replay.gui.widgets.video_list_card import VideoListCard
from splat_replay.gui.widgets.video_preview_card import VideoPreviewCard
from splat_replay.shared.logger import get_logger


class MainWindow:
    """メイン録画画面"""

    def __init__(self):
        """
        メインウィンドウを初期化

        Args:
            controller: アプリケーションのコントローラー
        """
        self.logger = get_logger()
        self.settings_dialog = None
        self._closing = False

        self.icon_path = (
            Path(__file__).parent.parent
            / ".."
            / ".."
            / ".."
            / "assets"
            / "icon.png"
        ).resolve()

        # tkinter ルートウィンドウを作成
        enable_high_dpi_awareness()
        self.window = ttk.Window(
            title="Splat Replay",
            themename="darkly",
            iconphoto=str(self.icon_path),
            size=(1600, 1100),
            minsize=(1200, 1100),
        )
        self.controller = GUIApplicationController(self.window)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close_request)

        self._setup_style()
        self._setup_menu()
        self._setup_content()
        self._setup_bindings()

        self.controller.add_detected_power_off_listener(
            self._on_detected_power_off
        )

        self.controller.start_auto_recorder()

        self.logger.info("メインウィンドウが初期化されました")

    def run_loop(self) -> None:
        self.window.mainloop()

    def start_auto_editor_and_uploader(self) -> None:
        dlg = ProgressDialog(self.window, self.controller)
        # start tasks first, then show modal progress
        self.controller.start_auto_editor_and_uploader()
        dlg.show()
        self.controller.start_auto_recorder()

    def _on_detected_power_off(self) -> None:
        self.logger.warning("電源OFFが検出されました")

        if self.controller.behavior_settings.edit_after_power_off:
            result = Messagebox.yesno(
                "Switchの電源OFFを検出しました。\n自動編集・アップロード処理を開始しますか？",
                "確認",
                parent=self.window,
            )
            if result == "はい":
                self.start_auto_editor_and_uploader()

    def _setup_menu(self) -> None:
        menu_bar = ttk.Frame(self.window, style="dark.TFrame")
        menu_bar.pack(fill="x", side="top")

        def create_button(text: str, cmd: Callable[[], None]) -> ttk.Button:
            return ttk.Button(
                menu_bar,
                text=text,
                command=cmd,
                compound="left",
                style="dark.TButton",
            )

        button = create_button("⚙️ 設定", self.show_setting_dialog)
        button.pack(side="left", ipadx=5, ipady=5, padx=(1, 0), pady=1)

    def _setup_content(self) -> None:
        content = ttk.Frame(self.window)
        content.pack(fill="both", expand=True, padx=20, pady=20)

        top_section = ttk.Frame(content)
        top_section.pack(fill="both", expand=True, pady=(0, 5))

        top_left_section = ttk.Frame(top_section)
        top_left_section.pack(
            side="left", fill="both", expand=True, padx=(0, 5)
        )
        VideoPreviewCard(top_left_section, self.controller)

        top_right_section = ttk.Frame(top_section)
        top_right_section.pack(side="right", fill="both", padx=(5, 0))
        MetadataEditorCard(top_right_section, self.controller)

        bottom_section = ttk.Frame(content)
        bottom_section.pack(fill="both", expand=True, pady=(5, 0))
        self.video_list_card = VideoListCard(
            bottom_section,
            self.controller,
            self.show_edit_dialog,
            self.start_auto_editor_and_uploader,
        )

    def _setup_bindings(self) -> None:
        """キーボードショートカットを設定"""
        # 設定画面のショートカット
        self.window.bind(
            "<Control-comma>", lambda e: self.show_setting_dialog()
        )

        # リフレッシュのショートカット
        self.window.bind("<F5>", lambda e: self.video_list_card.refresh_list())

    def show_setting_dialog(self) -> None:
        """設定画面を開く"""
        try:
            self.settings_dialog = SettingsDialog(self.window, self.controller)
            self.settings_dialog.show()

        except Exception as e:
            self.logger.error(f"設定画面の表示でエラー: {e}")
            Messagebox.show_error(
                f"設定画面を開けませんでした: {e}", "エラー", alert=True
            )

    def show_edit_dialog(
        self, metadata: Dict[str, str | None]
    ) -> Optional[Dict[str, str]]:
        dialog = MetadataEditorDialog(self.window, metadata)
        dialog.show()
        result: Optional[Dict[str, str]] = dialog.result
        return result

    def _setup_style(self) -> None:
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family="メイリオ", size=10)

        theme = ThemeDefinition(
            "neon",
            {
                "primary": "#FFD700",
                "secondary": "#444444",
                "success": "#39FF14",
                "info": "#A020F0",
                "warning": "#FFD700",
                "danger": "#FF1493",
                "light": "#E0E0E0",
                "dark": "#303030",
                "bg": "#222222",
                "fg": "#ffffff",
                "selectbg": "#555555",
                "selectfg": "#ffffff",
                "border": "#222222",
                "inputfg": "#ffffff",
                "inputbg": "#2f2f2f",
                "active": "#FFD700",
            },
            "dark",
        )

        style = ttk.Style()
        style.load_user_theme(theme)
        self.window.style.theme_use("neon")

    # --- 終了処理 -------------------------------------------------
    def _on_close_request(self) -> None:
        """ウィンドウクローズ要求 (× / Alt+F4) を受けた際の処理。

        - 録画中/一時停止中なら確認ダイアログ
        - 二重実行防止
        - コントローラーの close() を呼んでリソース解放
        """
        if self._closing:
            return

        state = self.controller.get_current_record_state()
        if state in (RecordState.RECORDING, RecordState.PAUSED):
            result = Messagebox.yesno(
                "録画中です。アプリを終了しますか？\n(録画は停止されます)",
                "確認",
                parent=self.window,
            )
            if result != "はい":
                return

        self._closing = True
        self.logger.info("メインウィンドウ終了処理開始")

        # 設定ダイアログ等が開いていれば閉じる
        try:
            if (
                self.settings_dialog
                and self.settings_dialog.window.winfo_exists()
            ):
                self.settings_dialog.window.destroy()
        except Exception:
            pass

        # コントローラーのクリーンアップ
        try:
            self.controller.close()
        except Exception as e:
            self.logger.error(f"controller.close 失敗: {e}")

        # 最後にウィンドウ破棄
        try:
            self.window.destroy()
        except Exception:
            pass
        self.logger.info("メインウィンドウ終了処理完了")
