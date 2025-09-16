"""API で利用する小さなユーティリティ関数群。"""

from __future__ import annotations

import base64
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


def encode_path(path: Path) -> str:
    """Path を URL セーフな文字列へ変換する。"""

    raw = str(path).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_path(encoded: str) -> Path:
    """エンコード済み文字列を Path へ戻す。"""

    padding = "=" * (-len(encoded) % 4)
    data = base64.urlsafe_b64decode(encoded + padding)
    return Path(data.decode("utf-8"))


def normalize_payload(value: Any) -> Any:
    """イベントペイロードを JSON シリアライズ可能な形へ整形する。"""

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: normalize_payload(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_payload(v) for v in value]
    return value


__all__ = ["encode_path", "decode_path", "normalize_payload"]
