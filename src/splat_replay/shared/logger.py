"""structlog を用いたロガー設定モジュール。"""

from __future__ import annotations

import contextlib
import io
import logging
from typing import Iterator, cast
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder
from structlog.stdlib import BoundLogger

_initialized = False


def initialize_logger(
    log_dir: str = "logs", log_file: str = "splat-replay.log"
) -> None:
    """ログ設定を初回のみ初期化する。"""
    global _initialized
    if not _initialized:
        Path(log_dir).mkdir(parents=True, exist_ok=True)

        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=[
                CallsiteParameterAdder(
                    parameters=[
                        CallsiteParameter.MODULE,
                        CallsiteParameter.FUNC_NAME,
                        CallsiteParameter.LINENO,
                    ]
                ),
                structlog.processors.TimeStamper(
                    fmt="%Y-%m-%d %H:%M:%S", utc=False
                ),
                structlog.stdlib.add_log_level,
                structlog.processors.StackInfoRenderer(),
            ],
        )
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(ensure_ascii=False),
            foreign_pre_chain=[
                CallsiteParameterAdder(
                    parameters=[
                        CallsiteParameter.MODULE,
                        CallsiteParameter.FUNC_NAME,
                        CallsiteParameter.LINENO,
                    ]
                ),
                structlog.processors.TimeStamper(
                    fmt="%Y-%m-%d %H:%M:%S", utc=False
                ),
                structlog.stdlib.add_log_level,
                structlog.processors.StackInfoRenderer(),
            ],
        )

        # ルートロガーの設定
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()

        # 3rd-party noisy logs を抑制するフィルタ
        class _NoiseFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                msg = str(record.getMessage())
                path = str(getattr(record, "pathname", ""))
                module = str(getattr(record, "module", ""))
                # Drop obswsc websocket abnormal close stacktraces
                if (
                    "connection closed (" in msg
                    and module == "client"
                    and path.replace("/", "\\").endswith("obswsc\\client.py")
                ):
                    return False
                return True

        # コンソール用ハンドラー（色付き）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(_NoiseFilter())
        root_logger.addHandler(console_handler)

        # ファイル出力用ハンドラー（JSON）
        file_handler = TimedRotatingFileHandler(
            filename=f"{log_dir}/{log_file}",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(_NoiseFilter())
        root_logger.addHandler(file_handler)

        # structlog のグローバル設定
        structlog.configure(
            processors=[
                CallsiteParameterAdder(
                    parameters=[
                        CallsiteParameter.MODULE,
                        CallsiteParameter.FUNC_NAME,
                        CallsiteParameter.LINENO,
                    ]
                ),
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(
                    fmt="%Y-%m-%d %H:%M:%S", utc=False
                ),
                structlog.processors.StackInfoRenderer(),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=BoundLogger,
            cache_logger_on_first_use=True,
        )
        _initialized = True


def get_logger() -> BoundLogger:
    """初期化済みロガーを取得する。"""
    if not _initialized:
        initialize_logger()
    return cast(BoundLogger, structlog.get_logger())


@contextlib.contextmanager
def buffer_console_logs() -> Iterator[io.StringIO]:
    """コンソールログ出力を一時的にバッファし、終了時にまとめて出力する。"""
    root_logger = logging.getLogger()
    orig_handlers = list(root_logger.handlers)
    stream_handlers = [
        h for h in orig_handlers if type(h) is logging.StreamHandler
    ]
    log_buffer = io.StringIO()
    buffer_handlers = []
    for h in stream_handlers:
        buffer_handler = logging.StreamHandler(log_buffer)
        buffer_handler.setLevel(h.level)
        buffer_handler.setFormatter(h.formatter)
        root_logger.removeHandler(h)
        root_logger.addHandler(buffer_handler)
        buffer_handlers.append(buffer_handler)
    try:
        yield log_buffer
    finally:
        for bh in buffer_handlers:
            root_logger.removeHandler(bh)
        for h in stream_handlers:
            root_logger.addHandler(h)
        print(log_buffer.getvalue(), end="")
        log_buffer.close()
