"""PyInstaller 用の hidden imports を root lazy export 定義から生成する。"""

from __future__ import annotations

from splat_replay.infrastructure import (
    _LAZY_EXPORTS as INFRASTRUCTURE_LAZY_EXPORTS,
)


def _expand_hiddenimport_chain(module_name: str) -> list[str]:
    parts = module_name.split(".")
    start_index = 3 if len(parts) >= 3 else len(parts)
    return [
        ".".join(parts[:index]) for index in range(start_index, len(parts) + 1)
    ]


def collect_pyinstaller_hiddenimports() -> list[str]:
    """root lazy import で参照する package / module を重複なく列挙する。"""
    hiddenimports: list[str] = []
    seen: set[str] = set()
    for module_name, _attribute_name in INFRASTRUCTURE_LAZY_EXPORTS.values():
        resolved_module_name = f"splat_replay.infrastructure{module_name}"
        for hiddenimport in _expand_hiddenimport_chain(resolved_module_name):
            if hiddenimport in seen:
                continue
            seen.add(hiddenimport)
            hiddenimports.append(hiddenimport)
    return hiddenimports


__all__ = ["collect_pyinstaller_hiddenimports"]
