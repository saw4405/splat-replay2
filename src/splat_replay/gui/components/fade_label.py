import tkinter as tk

import ttkbootstrap as ttk


def _to_hex_from_tkcolor(widget: tk.Widget, color: str) -> str:
    """'SystemButtonFace' 等の色名 → #rrggbb へ変換"""
    r, g, b = widget.winfo_rgb(color)  # 0..65535
    return f"#{r // 256:02x}{g // 256:02x}{b // 256:02x}"


def _hex_to_rgb(hexstr: str) -> tuple[int, int, int]:
    hexstr = hexstr.lstrip("#")
    return int(hexstr[0:2], 16), int(hexstr[2:4], 16), int(hexstr[4:6], 16)


def _mix_hex(start: str, end: str, t: float) -> str:
    """2色を t(0..1) で線形補間"""
    ar, ag, ab = _hex_to_rgb(start)
    br, bg, bb = _hex_to_rgb(end)
    r = round(ar + (br - ar) * t)
    g = round(ag + (bg - ag) * t)
    b = round(ab + (bb - ab) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _ease_in_out_quad(t: float) -> float:
    return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t


class FadeLabel(ttk.Label):
    """
    段階的に文字色を変えてフェードイン/アウトを実現する ttk.Label
    - ラベル専用のスタイルを自動生成（他のラベルに影響しません）
    - 背景色の自動推定（テーマに依存してもOK）
    """

    def __init__(
        self,
        master=None,
        text: str = "",
        *,
        duration: int = 300,  # アニメ全体時間(ms)
        steps: int = 20,  # ステップ数
        target_fg: str | None = None,  # 目標の文字色（Noneならテーマの前景色）
        base_style: str = "TLabel",
        **kwargs,
    ):
        super().__init__(master, text=text, **kwargs)
        self._job = None
        self._duration = max(1, duration)
        self._steps = max(1, steps)
        self._base_style = base_style
        self._style = ttk.Style()

        # このラベル専用スタイル名（一意）
        self._style_name = f"FadeLabel{self.winfo_id()}.{base_style}"
        # ベースからスタイルを派生
        self._style.configure(self._style_name)
        self.configure(style=self._style_name)

        # 色確定（背景/前景）
        self._bg = self._resolve_background()
        self._fg = target_fg or self._resolve_foreground()

        # 初期は目標の前景色にしておく
        self._style.configure(self._style_name, foreground=self._fg)

    # ---- public API -------------------------------------------------
    def fade_in(self, *, text: str | None = None):
        """背景色→文字色へ補間してフェードイン"""
        if text is not None:
            self.configure(text=text)
        self._start_anim(start=self._bg, end=self._fg)

    def fade_out(self):
        """文字色→背景色へ補間してフェードアウト"""
        self._start_anim(start=self._current_fg(), end=self._bg)

    def stop(self):
        """途中停止（色はそのまま）"""
        if self._job:
            self.after_cancel(self._job)
            self._job = None

    # ---- internals --------------------------------------------------
    def _resolve_background(self) -> str:
        # 1) スタイルから背景取得
        bg = self._style.lookup(self._base_style, "background")
        if not bg:
            # 2) ウィジェット背景 → トップレベル背景 → 白
            bg = (
                self.cget("background")
                or self.winfo_toplevel().cget("background")
                or "#ffffff"
            )
        # 色名→hex（すでに#rrggbbならそのまま）
        return bg if bg.startswith("#") else _to_hex_from_tkcolor(self, bg)

    def _resolve_foreground(self) -> str:
        fg = self._style.lookup(self._base_style, "foreground")
        if not fg:
            fg = "#000000"
        return fg

    def _current_fg(self) -> str:
        fg = self._style.lookup(self._style_name, "foreground")
        if fg and fg.startswith("#"):
            return fg
        return self._fg

    def _start_anim(self, *, start: str, end: str):
        self.stop()
        interval = self._duration // self._steps
        # スナップショット
        steps = self._steps

        def step(i: int):
            t = _ease_in_out_quad(i / steps)
            color = _mix_hex(start, end, t)
            self._style.configure(self._style_name, foreground=color)
            if i < steps:
                self._job = self.after(interval, lambda: step(i + 1))
            else:
                # 最終色で固定
                self._style.configure(self._style_name, foreground=end)
                self._job = None

        step(0)
