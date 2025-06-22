from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pytest

# ``src`` ディレクトリを ``sys.path`` へ追加
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))  # noqa: E402

from splat_replay.infrastructure.analyzers.frame_analyzer import FrameAnalyzer  # noqa: E402
from splat_replay.infrastructure.analyzers.splatoon_battle_analyzer import BattleFrameAnalyzer  # noqa: E402
from splat_replay.shared.config import ImageMatchingSettings  # noqa: E402
import cv2  # noqa: E402


# config の YAML を読み込み、必要なパスをテスト用に上書きする
BASE_DIR = Path(__file__).resolve().parent
MATCHER_SETTINGS = ImageMatchingSettings.load_from_yaml(
    BASE_DIR.parent / "config" / "image_matching.yaml"
)

# テスト用テンプレートへのパスを設定し直す
TEMPLATE_DIR = BASE_DIR / "fixtures" / "templates"


@pytest.fixture()
def analyzer() -> FrameAnalyzer:
    """レジストリを利用する ``FrameAnalyzer`` を返す。"""
    plugin = BattleFrameAnalyzer(MATCHER_SETTINGS)
    return FrameAnalyzer(plugin, MATCHER_SETTINGS)


@pytest.fixture()
def load_image() -> Callable[[str], np.ndarray]:
    """フィクスチャ画像を読み込むヘルパ。"""

    def _load(filename: str) -> np.ndarray:
        image_path = TEMPLATE_DIR / filename
        print(f"読み込む画像: {image_path}")
        image = cv2.imread(str(image_path))
        if image is None:
            pytest.skip(f"画像ファイルが存在しないか読み込めません: {image_path}")
        return image
    return _load


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("power_off.png", True),
        ("loading_1.png", False),
    ],
)
def test_detect_power_off(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """電源OFF 判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_power_off(frame)
    assert result == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_finish_1.png", True),
        ("battle_finish_2.png", True),
        ("battle_finish_3.png", True),
        ("battle_finish_4.png", True),
        ("battle_finish_5.png", True),
        ("battle_finish_6.png", True),
        ("battle_finish_7.png", True),
        ("battle_finish_8.png", True),
        ("battle_finish_9.png", True),
        ("battle_finish_10.png", True),
        ("battle_finish_11.png", False),
        ("loading_1.png", False)
    ],
)
def test_detect_battle_finish(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """FINISH 表示判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_battle_finish(frame)
    assert result == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_stop_1.png", True),
        ("battle_stop_2.png", True),
        ("battle_stop_3.png", False),
        ("battle_stop_4.png", False),
    ],
)
def test_detect_battle_stop(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """バトル終了画面判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_battle_stop(frame)
    assert result == expected
