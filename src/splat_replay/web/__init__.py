"""Web API モジュール。"""

from __future__ import annotations

from fastapi import FastAPI

from splat_replay.web.app import create_app

__all__ = ["FastAPI", "create_app"]
