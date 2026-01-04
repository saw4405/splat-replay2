"""CLI logging helpers."""

from __future__ import annotations

import contextlib
import io
import logging
from typing import Iterator


@contextlib.contextmanager
def buffer_console_logs() -> Iterator[io.StringIO]:
    """Buffer console logs and flush them after the wrapped block."""
    root_logger = logging.getLogger()
    orig_handlers = list(root_logger.handlers)
    stream_handlers = [
        handler
        for handler in orig_handlers
        if type(handler) is logging.StreamHandler
    ]
    log_buffer = io.StringIO()
    buffer_handlers = []
    for handler in stream_handlers:
        buffer_handler = logging.StreamHandler(log_buffer)
        buffer_handler.setLevel(handler.level)
        buffer_handler.setFormatter(handler.formatter)
        root_logger.removeHandler(handler)
        root_logger.addHandler(buffer_handler)
        buffer_handlers.append(buffer_handler)
    try:
        yield log_buffer
    finally:
        for handler in buffer_handlers:
            root_logger.removeHandler(handler)
        for handler in stream_handlers:
            root_logger.addHandler(handler)
        print(log_buffer.getvalue(), end="")
        log_buffer.close()
