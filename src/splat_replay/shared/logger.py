"""structlog を用いたロガー設定。"""

from __future__ import annotations

import logging

import structlog


def configure_logging() -> None:
    """基本的なロギング設定を行う。"""

    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """名前付きロガーを取得する。"""

    return structlog.get_logger(name)
