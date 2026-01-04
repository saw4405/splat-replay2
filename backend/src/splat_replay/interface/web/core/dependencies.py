"""Dependency injection setup for Web API.

FastAPI の依存性注入（Depends）用の関数を提供する。
Clean Architecture の原則に従い、ユースケースの注入のみを行う。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer

# グローバル変数（app.py で初期化される）
_server: WebAPIServer | None = None


def set_server(server: WebAPIServer) -> None:
    """WebAPIServer インスタンスをグローバルに設定する。

    Args:
        server: WebAPIServer インスタンス
    """
    global _server
    _server = server


def get_server() -> WebAPIServer:
    """WebAPIServer インスタンスを取得する（依存性注入用）。

    Returns:
        WebAPIServer インスタンス

    Raises:
        RuntimeError: サーバーが初期化されていない場合
    """
    if _server is None:
        raise RuntimeError("Server not initialized. Call set_server() first.")
    return _server


__all__ = [
    "set_server",
    "get_server",
]
