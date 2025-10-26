"""Web interface for Splat Replay."""

from __future__ import annotations

__all__ = ["create_app", "WebServer"]

from splat_replay.web.server import WebServer, create_app
