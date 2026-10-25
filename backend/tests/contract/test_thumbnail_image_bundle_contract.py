"""macOSの配布資産選択が6ルール画像を収録する契約。"""

from pathlib import Path
import ast
from typing import Any
import pytest
from splat_replay.domain.models import Rule

pytestmark = pytest.mark.contract


def test_macos_package_selects_all_six_rule_images() -> None:
    backend = Path(__file__).resolve().parents[2]
    tree = ast.parse(
        (backend / "packaging/splat-replay-webview.spec").read_text()
    )
    selection = next(
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "is_macos"
    )
    scope: dict[str, Any] = {
        "Path": Path,
        "backend_root": backend,
        "datas": [],
        "is_macos": True,
    }
    exec(
        compile(
            ast.Module(body=[selection], type_ignores=[]),
            "package-asset-selection",
            "exec",
        ),
        scope,
    )
    datas = scope["datas"]
    for rule in Rule:
        source = (
            backend / f"assets/thumbnail/rule-labels/{rule.name.lower()}.png"
        )
        assert (str(source), "assets/thumbnail/rule-labels") in datas
