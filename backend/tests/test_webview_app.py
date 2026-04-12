from __future__ import annotations

from pathlib import Path

from splat_replay.interface.gui.webview_app import build_frontend_entry_url


def test_build_frontend_entry_url_uses_index_mtime_cache_buster(
    tmp_path: Path,
) -> None:
    """frontend の entry URL は index.html 更新で変化する。"""
    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    index_html = frontend_dist / "index.html"
    index_html.write_text(
        "<!doctype html><title>fresh</title>", encoding="utf-8"
    )

    url = build_frontend_entry_url("http://127.0.0.1:8000", frontend_dist)

    assert url == (
        "http://127.0.0.1:8000/?frontend="
        f"{index_html.stat().st_mtime_ns}-{index_html.stat().st_size}"
    )
