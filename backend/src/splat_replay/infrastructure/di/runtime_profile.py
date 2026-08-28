"""DI 構成時に使用する実行プロファイル。"""

from __future__ import annotations

import os
from enum import StrEnum

RUNTIME_PROFILE_ENV = "SPLAT_REPLAY_RUNTIME_PROFILE"


class RuntimeProfile(StrEnum):
    """外部アダプターの構成方針。"""

    LIVE = "live"
    REPLAY = "replay"


def resolve_runtime_profile(value: str | None = None) -> RuntimeProfile:
    """環境変数または明示値から実行プロファイルを解決する。"""
    raw_value = (
        os.getenv(RUNTIME_PROFILE_ENV, RuntimeProfile.LIVE)
        if value is None
        else value
    )
    normalized = raw_value.strip().lower()
    try:
        return RuntimeProfile(normalized)
    except ValueError as exc:
        raise ValueError(
            f"{RUNTIME_PROFILE_ENV} は 'live' または 'replay' を指定してください: "
            f"{raw_value!r}"
        ) from exc
