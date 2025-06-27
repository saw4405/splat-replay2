from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

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
        ("matching_1.png", True),
        ("battle_result_1.png", False),
    ],
)
def test_detect_matching_start(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """マッチング開始 判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_matching_start(frame)
    assert result == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("schedule_change_1.png", True),
        ("loading_1.png", False),
    ],
)
def test_detect_schedule_change(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """スケジュール変更 判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_schedule_change(frame)
    assert result == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_start_1.png", True),
        ("battle_start_2.png", True),
        ("battle_start_3.png", False),
        ("matching_1.png", False)
    ],
)
def test_detect_battle_start(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """バトル開始 判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_battle_start(frame)
    assert result == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_abort_1.png", True),
        ("battle_result_1.png", False)
    ],
)
def test_detect_battle_abort(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """バトル中断 判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_battle_abort(frame)
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
        ("battle_judgement_1.png", True),
        ("battle_judgement_2.png", True),
        ("battle_judgement_3.png", False),
        ("battle_judgement_4.png", False),
    ],
)
def test_detect_battle_finish_end(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """FINISH 表示判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_battle_finish_end(frame)
    assert result == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_judgement_1.png", "win"),
        ("battle_judgement_2.png", "lose"),
        ("battle_judgement_3.png", "lose"),
        ("battle_judgement_4.png", None),
    ],
)
def test_extract_battle_judgement(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: Optional[str]
) -> None:
    """FINISH 表示判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.extract_battle_judgement(frame)
    assert result == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("loading_1.png", True),
        ("power_off.png", False)
    ],
)
def test_detect_loading(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """ローディング判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_loading(frame)
    assert result == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_result_1.png", True),
        # ("battle_result_2.png", True), # 未対応
        ("battle_result_3.png", False),
        ("battle_result_4.png", False),
    ],
)
def test_detect_battle_result(
    analyzer: FrameAnalyzer, load_image: Callable[[str], np.ndarray], filename: str, expected: bool
) -> None:
    """バトル終了画面判定の結果を確認する。"""
    frame = load_image(filename)
    result = analyzer.detect_battle_result(frame)
    assert result == expected


plugin = BattleFrameAnalyzer(MATCHER_SETTINGS)
a = FrameAnalyzer(plugin, MATCHER_SETTINGS)


image_path = TEMPLATE_DIR / "battle_judgement_2.png"
image = cv2.imread(str(image_path))
result = a.extract_battle_judgement(image)
print(f"Battle finish detected: {result}")
