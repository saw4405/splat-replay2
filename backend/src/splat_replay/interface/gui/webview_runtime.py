"""WebView runtime configuration helpers."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Literal


WEBVIEW2_BROWSER_ARGUMENTS_ENV = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"
WEBVIEW2_DISABLE_GPU_FLAG = "--disable-gpu"
WebViewRenderMode = Literal["cpu", "gpu"]


def normalize_webview_render_mode(value: str | None) -> WebViewRenderMode:
    """描画モードの入力値を有効な内部値へ正規化する。"""
    if isinstance(value, str) and value.lower() == "gpu":
        return "gpu"
    if isinstance(value, str) and value.lower() == "cpu":
        return "cpu"
    return "gpu"


def configure_webview2_browser_arguments(
    env: MutableMapping[str, str], *, platform: str, render_mode: str
) -> str | None:
    """Windows の WebView2 に描画モードに応じたブラウザ引数を反映する。

    既存引数は保持しつつ、`cpu` では `--disable-gpu` を追加し、
    `gpu` では `--disable-gpu` を除去する。

    Args:
        env: 更新対象の環境変数マッピング
        platform: 実行プラットフォーム
        render_mode: 描画モード

    Returns:
        設定後の引数文字列。Windows 以外では ``None`` を返す。
    """
    if platform != "win32":
        return None

    mode = normalize_webview_render_mode(render_mode)
    existing = env.get(WEBVIEW2_BROWSER_ARGUMENTS_ENV, "").strip()
    arguments = [part for part in existing.split() if part]

    if mode == "cpu" and WEBVIEW2_DISABLE_GPU_FLAG not in arguments:
        arguments.append(WEBVIEW2_DISABLE_GPU_FLAG)
    if mode == "gpu":
        arguments = [
            part for part in arguments if part != WEBVIEW2_DISABLE_GPU_FLAG
        ]

    if arguments:
        configured = " ".join(arguments)
        env[WEBVIEW2_BROWSER_ARGUMENTS_ENV] = configured
        return configured

    env.pop(WEBVIEW2_BROWSER_ARGUMENTS_ENV, None)
    return ""


__all__ = [
    "WEBVIEW2_BROWSER_ARGUMENTS_ENV",
    "WEBVIEW2_DISABLE_GPU_FLAG",
    "WebViewRenderMode",
    "configure_webview2_browser_arguments",
    "normalize_webview_render_mode",
]
