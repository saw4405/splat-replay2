"""ウィンドウ位置/サイズ関連の共通ユーティリティ."""

from __future__ import annotations

import os
import tkinter as tk
from typing import Callable, Optional


def center_to_parent(
    win: tk.Toplevel,
    parent: Optional[tk.Misc] = None,
    *,
    offset_y: int = 0,
    delay_ms: int = 0,
    retry: int = 1,
    debug: bool = False,
    extra_passes: int = 2,
) -> None:
    """親(または画面)中央へ配置する汎用関数。

    レイアウト未確定 (幅/高さ=1) の場合は ``after`` で再試行し、
    指定回数 ``retry`` だけ再センタリングする。

    Args:
        win: 対象 Toplevel
        parent: 親ウィジェット (未指定なら最上位を推定)
        offset_y: 垂直方向微調整
        delay_ms: 初回実行を遅延させるミリ秒
        retry: 再センタリング試行回数 (0 なら一度のみ)
    """

    # デバッグロガー初期化 (環境変数か引数で有効化)
    debug_enabled = debug or os.environ.get("SPLAT_CENTER_DEBUG") == "1"
    log_func: Optional[Callable[[str, Optional[dict[str, object]]], None]] = (
        None
    )
    if debug_enabled:
        try:  # 遅延 import (循環回避)
            from splat_replay.shared.logger import get_logger

            base_logger = get_logger().bind(component="center_to_parent")

            def _logger(
                msg: str, data: Optional[dict[str, object]] = None
            ) -> None:
                # debug だとユーザー環境で出ない可能性があるので info に昇格
                base_logger.info(msg, **(data or {}))

            log_func = _logger
        except Exception:
            # フォールバック: print
            def _fallback_logger(
                msg: str, data: Optional[dict[str, object]] = None
            ) -> None:
                print(f"[center_to_parent] {msg} {data or ''}")

            log_func = _fallback_logger

    def _log(msg: str, **data: object) -> None:
        if log_func:
            log_func(msg, data)

    def _do_center(remain: int) -> None:
        try:
            base = parent
            if base is None:
                # master か最上位ウィンドウを推定
                try:
                    base = win.master
                except Exception:
                    base = None
            if base is not None and not isinstance(base, (tk.Tk, tk.Toplevel)):
                try:
                    base = base.winfo_toplevel()
                except Exception:
                    base = None

            if base and isinstance(base, (tk.Tk, tk.Toplevel)):
                base.update_idletasks()
                px = base.winfo_rootx()
                py = base.winfo_rooty()
                pw = base.winfo_width()
                ph = base.winfo_height()
                # 未 realized の場合 (幅/高さが極端に小さい)
                if pw <= 1 or ph <= 1:
                    screen = win.winfo_screenwidth(), win.winfo_screenheight()
                    px, py, pw, ph = 0, 0, screen[0], screen[1]
            else:
                screen = win.winfo_screenwidth(), win.winfo_screenheight()
                px, py, pw, ph = 0, 0, screen[0], screen[1]

            win.update_idletasks()
            ww = max(win.winfo_width(), win.winfo_reqwidth())
            wh = max(win.winfo_height(), win.winfo_reqheight())
            if ww <= 1 or wh <= 1:
                # まだ決まっていない: 再試行
                if remain > 0:
                    _log(
                        "size unresolved; retry",
                        remain=remain,
                        width=ww,
                        height=wh,
                    )
                    win.after(30, lambda: _do_center(remain - 1))
                return
            x = px + (pw - ww) // 2
            y = py + (ph - wh) // 2 + offset_y
            if y < 0:
                y = 0
            win.geometry(f"{ww}x{wh}+{x}+{y}")
            _log(
                "center applied",
                parent_rect=(px, py, pw, ph),
                window_size=(ww, wh),
                pos=(x, y),
                offset_y=offset_y,
                remain=remain,
            )
            # 内容遅延膨張 (ttk.Notebook 等) 対応で追加パス
            extra_left = getattr(_do_center, "_extra_left", extra_passes)
            if extra_left > 0:
                setattr(_do_center, "_extra_left", extra_left - 1)
                win.after(120, lambda: _do_center(0))
        except Exception as exc:
            _log("error", error=str(exc))
            pass

    if delay_ms > 0:
        _log(
            "scheduling initial center",
            delay_ms=delay_ms,
            retry=retry,
            extra_passes=extra_passes,
        )
        try:
            win.after(delay_ms, lambda: _do_center(retry))
        except Exception as e:
            _log("schedule_failed", error=str(e))
    else:
        _do_center(retry)
