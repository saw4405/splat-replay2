from __future__ import annotations

from collections.abc import Mapping

from splat_replay.bootstrap.pyinstaller_hiddenimports import (
    collect_pyinstaller_hiddenimports,
)
from splat_replay.infrastructure import (
    _LAZY_EXPORTS as INFRASTRUCTURE_LAZY_EXPORTS,
)
from splat_replay.infrastructure.adapters import (
    _LAZY_EXPORTS as ADAPTERS_LAZY_EXPORTS,
)
from splat_replay.infrastructure.adapters.audio import (
    _LAZY_EXPORTS as AUDIO_LAZY_EXPORTS,
)


def _resolve_module_name(package_name: str, module_name: str) -> str:
    if module_name.startswith("."):
        return f"{package_name}{module_name}"
    return module_name


def _expected_hiddenimports(module_name: str) -> list[str]:
    parts = module_name.split(".")
    start_index = 3 if len(parts) >= 3 else len(parts)
    return [
        ".".join(parts[:index]) for index in range(start_index, len(parts) + 1)
    ]


def test_collect_pyinstaller_hiddenimports_covers_all_lazy_exports() -> None:
    hiddenimports = set(collect_pyinstaller_hiddenimports())
    lazy_export_packages: tuple[
        tuple[str, Mapping[str, tuple[str, str]]], ...
    ] = (
        ("splat_replay.infrastructure", INFRASTRUCTURE_LAZY_EXPORTS),
        ("splat_replay.infrastructure.adapters", ADAPTERS_LAZY_EXPORTS),
        ("splat_replay.infrastructure.adapters.audio", AUDIO_LAZY_EXPORTS),
    )

    for package_name, lazy_exports in lazy_export_packages:
        for module_name, _attribute_name in lazy_exports.values():
            resolved_module_name = _resolve_module_name(
                package_name, module_name
            )
            missing = [
                name
                for name in _expected_hiddenimports(resolved_module_name)
                if name not in hiddenimports
            ]
            assert not missing, (
                "PyInstaller hiddenimports に lazy import の収集漏れがあります: "
                f"{resolved_module_name} missing={missing}"
            )


def test_collect_pyinstaller_hiddenimports_contains_capture_package_chain() -> (
    None
):
    hiddenimports = set(collect_pyinstaller_hiddenimports())

    assert "splat_replay.infrastructure.adapters.capture" in hiddenimports
    assert (
        "splat_replay.infrastructure.adapters.capture.capture" in hiddenimports
    )
