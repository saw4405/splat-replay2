"""app_factory の振る舞いテスト。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.bootstrap.web_app import build_web_api_server
from splat_replay.infrastructure.di import configure_container
from splat_replay.interface.web.app_factory import create_app


def test_create_app_allows_missing_frontend_assets_subdir(
    tmp_path: Path,
) -> None:
    """frontend/dist/assets が無くても API アプリを生成できる。"""
    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    (frontend_dist / "index.html").write_text(
        "<!doctype html><title>test</title>", encoding="utf-8"
    )

    container = configure_container()
    server = build_web_api_server(container)
    server.project_root = tmp_path

    app = create_app(server, enable_lifespan=False)

    assert app is not None
