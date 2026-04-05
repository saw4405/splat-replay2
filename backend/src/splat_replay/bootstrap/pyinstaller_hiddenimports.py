"""PyInstaller 用の hidden imports を lazy export 定義から生成する。"""

from __future__ import annotations

from collections.abc import Mapping

from splat_replay.infrastructure import (
    _LAZY_EXPORTS as INFRASTRUCTURE_LAZY_EXPORTS,
)
from splat_replay.infrastructure.adapters import (
    _LAZY_EXPORTS as ADAPTERS_LAZY_EXPORTS,
)
from splat_replay.infrastructure.adapters.audio import (
    _LAZY_EXPORTS as AUDIO_LAZY_EXPORTS,
)

_LAZY_EXPORT_PACKAGES: tuple[
    tuple[str, Mapping[str, tuple[str, str]]], ...
] = (
    ("splat_replay.infrastructure", INFRASTRUCTURE_LAZY_EXPORTS),
    ("splat_replay.infrastructure.adapters", ADAPTERS_LAZY_EXPORTS),
    ("splat_replay.infrastructure.adapters.audio", AUDIO_LAZY_EXPORTS),
)


def _resolve_module_name(package_name: str, module_name: str) -> str:
    if module_name.startswith("."):
        return f"{package_name}{module_name}"
    return module_name


def _expand_hiddenimport_chain(module_name: str) -> list[str]:
    parts = module_name.split(".")
    start_index = 3 if len(parts) >= 3 else len(parts)
    return [
        ".".join(parts[:index]) for index in range(start_index, len(parts) + 1)
    ]


def collect_pyinstaller_hiddenimports() -> list[str]:
    """lazy import で参照する package / module を重複なく列挙する。"""
    hiddenimports: list[str] = []
    seen: set[str] = set()
    for package_name, lazy_exports in _LAZY_EXPORT_PACKAGES:
        for module_name, _attribute_name in lazy_exports.values():
            resolved_module_name = _resolve_module_name(
                package_name, module_name
            )
            for hiddenimport in _expand_hiddenimport_chain(
                resolved_module_name
            ):
                if hiddenimport in seen:
                    continue
                seen.add(hiddenimport)
                hiddenimports.append(hiddenimport)
    return hiddenimports


__all__ = ["collect_pyinstaller_hiddenimports"]
