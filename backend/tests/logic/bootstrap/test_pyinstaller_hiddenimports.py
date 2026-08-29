from __future__ import annotations

from splat_replay.bootstrap.pyinstaller_hiddenimports import (
    collect_pyinstaller_hiddenimports,
)
from splat_replay.infrastructure import (
    _LAZY_EXPORTS as INFRASTRUCTURE_LAZY_EXPORTS,
)


def _expected_hiddenimports(module_name: str) -> list[str]:
    parts = module_name.split(".")
    start_index = 3 if len(parts) >= 3 else len(parts)
    return [
        ".".join(parts[:index]) for index in range(start_index, len(parts) + 1)
    ]


def test_collect_pyinstaller_hiddenimports_covers_all_lazy_exports() -> None:
    hiddenimports = set(collect_pyinstaller_hiddenimports())
    for module_name, _attribute_name in INFRASTRUCTURE_LAZY_EXPORTS.values():
        resolved_module_name = f"splat_replay.infrastructure{module_name}"
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


def test_collect_pyinstaller_hiddenimports_contains_runtime_leaf_modules() -> (
    None
):
    hiddenimports = set(collect_pyinstaller_hiddenimports())
    required_leaf_modules = {
        "splat_replay.infrastructure.adapters.medal_detection.recognizer",
        "splat_replay.infrastructure.adapters.medal_detection.replay_recognizer",
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer",
        "splat_replay.infrastructure.adapters.weapon_detection.replay_recognizer",
    }

    assert required_leaf_modules <= hiddenimports
