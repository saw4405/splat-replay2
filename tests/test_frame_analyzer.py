from __future__ import annotations

# ruff: noqa: E402
import sys
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np
import pytest

# ``src`` ディレクトリを ``sys.path`` へ追加
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))  # noqa: E402

from splat_replay.domain.models import (
    XP,
    BattleResult,
    GameMode,
    Match,
    RateBase,
    Rule,
    Stage,
    Udemae,
    as_frame,
)  # noqa: E402
from splat_replay.domain.services.analyzers import (
    BattleFrameAnalyzer,
    FrameAnalyzer,
    SalmonFrameAnalyzer,
)  # noqa: E402
from splat_replay.infrastructure import (
    ImageEditor,
    MatcherRegistry,
    TesseractOCR,
)  # noqa: E402
from splat_replay.shared.config import ImageMatchingSettings  # noqa: E402
from splat_replay.shared.logger import get_logger  # noqa: E402

# config の YAML を読み込み、必要なパスをテスト用に上書きする
BASE_DIR = Path(__file__).resolve().parent
MATCHER_SETTINGS = ImageMatchingSettings.load_from_yaml(
    BASE_DIR.parent / "config" / "image_matching.yaml"
)

# テスト用テンプレートへのパスを設定し直す
TEMPLATE_DIR = BASE_DIR / "fixtures" / "templates"


def create_analyzer() -> FrameAnalyzer:
    """レジストリを利用する ``FrameAnalyzer`` を返す。"""
    matcher_registry = MatcherRegistry(MATCHER_SETTINGS)
    ocr = TesseractOCR()

    def image_editor_factory(image):
        return ImageEditor(image)

    logger = get_logger()
    battle = BattleFrameAnalyzer(
        matcher_registry, ocr, image_editor_factory, logger
    )
    salmon = SalmonFrameAnalyzer(matcher_registry)
    analyzer = FrameAnalyzer(battle, salmon, matcher_registry)
    return analyzer


@pytest.fixture()
def analyzer() -> FrameAnalyzer:
    return create_analyzer()


@pytest.fixture()
def load_image() -> Callable[[str], np.ndarray]:
    """フィクスチャ画像を読み込むヘルパ。"""

    def _load(filename: str) -> np.ndarray:
        image_path = TEMPLATE_DIR / filename
        image = cv2.imread(str(image_path))
        if image is None:
            pytest.skip(
                f"画像ファイルが存在しないか読み込めません: {image_path}"
            )
        return image

    return _load


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("power_off.png", True),
        ("loading_1.png", False),
    ],
)
async def test_detect_power_off(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """電源OFF 判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_power_off(frame)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("match_select_regular.png", True),
        ("match_select_challenge.png", True),
        ("match_select_anarchy_battle.png", True),
        ("match_select_x_battle.png", True),
        ("match_select_splatfest_battle_1.png", True),
        ("match_select_splatfest_battle_2.png", True),
    ],
)
async def test_detect_match_select(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """マッチ選択画面の判定結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_match_select(frame)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("match_select_regular.png", GameMode.BATTLE),
        ("match_select_anarchy_battle.png", GameMode.BATTLE),
        ("match_select_x_battle.png", GameMode.BATTLE),
        ("match_select_challenge.png", GameMode.BATTLE),
        ("match_select_splatfest_battle_1.png", GameMode.BATTLE),
        ("match_select_splatfest_battle_2.png", GameMode.BATTLE),
        ("power_off.png", None),
    ],
)
async def test_extract_game_mode(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: GameMode | None,
) -> None:
    """ゲームモードの抽出結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.extract_game_mode(frame)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("match_select_regular.png", Match.REGULAR),
        ("match_select_anarchy_battle.png", Match.ANARCHY),
        ("match_select_x_battle.png", Match.X),
        ("match_select_challenge.png", Match.CHALLENGE),
        ("match_select_splatfest_battle_1.png", Match.SPLATFEST),
        ("match_select_splatfest_battle_2.png", Match.SPLATFEST),
        # トリカラマッチ画像なし
    ],
)
async def test_extract_match_select(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: GameMode,
) -> None:
    """マッチの抽出結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.extract_match_select(frame, GameMode.BATTLE)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("rate_XP1971.9.png", XP(1971.9)),
        ("rate_XP2033.9.png", XP(2033.9)),
        ("rate_S.png", Udemae("S")),
        ("rate_S+.png", Udemae("S+")),
        ("rate_None.png", None),
    ],
)
async def test_extract_rate(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: RateBase,
) -> None:
    """レート取得の結果を確認する。"""
    frame = load_image(filename)
    if not await analyzer.detect_match_select(frame):
        pytest.fail("マッチ選択画面ではない")
    mode = await analyzer.extract_game_mode(frame)
    if mode is None:
        pytest.fail("モードが抽出できない")
        return
    result = await analyzer.extract_rate(frame, mode)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("matching_1.png", True),
        ("battle_result_1.png", False),
    ],
)
async def test_detect_matching_start(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """マッチング開始 判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_matching_start(frame)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("schedule_change_1.png", True),
        ("loading_1.png", False),
    ],
)
async def test_detect_schedule_change(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """スケジュール変更 判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_schedule_change(frame)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_start_1.png", True),
        ("battle_start_2.png", True),
        ("battle_start_3.png", True),
        ("battle_start_4.png", False),
        ("matching_1.png", False),
    ],
)
async def test_detect_battle_start(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """バトル開始 判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_session_start(frame, GameMode.BATTLE)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [("battle_abort_1.png", True), ("battle_result_1.png", False)],
)
async def test_detect_battle_abort(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """バトル中断 判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_session_abort(frame, GameMode.BATTLE)
    assert result == expected


@pytest.mark.asyncio
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
        ("battle_finish_11.png", True),
        ("battle_finish_12.png", False),
        ("loading_1.png", False),
    ],
)
async def test_detect_battle_finish(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """FINISH 表示判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_session_finish(frame, GameMode.BATTLE)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_judgement_1.png", True),
        ("battle_judgement_2.png", True),
        ("battle_judgement_3.png", True),
        ("battle_judgement_4.png", False),
        ("battle_judgement_5.png", False),
    ],
)
async def test_detect_battle_finish_end(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """FINISH 表示判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_session_finish_end(frame, GameMode.BATTLE)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_judgement_1.png", True),
        ("battle_judgement_2.png", True),
        ("battle_judgement_3.png", True),
        ("battle_judgement_4.png", False),
        ("battle_judgement_5.png", False),
        ("loading_1.png", False),
    ],
)
async def test_detect_battle_judgement(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """バトル判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_session_judgement(frame, GameMode.BATTLE)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_judgement_1.png", "win"),
        ("battle_judgement_2.png", "lose"),
        ("battle_judgement_3.png", "lose"),
        ("battle_judgement_4.png", "lose"),
        ("battle_judgement_5.png", None),
    ],
)
async def test_extract_battle_judgement(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: Optional[str],
) -> None:
    """FINISH 表示判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.extract_session_judgement(frame, GameMode.BATTLE)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [("loading_1.png", True), ("power_off.png", False)],
)
async def test_detect_loading(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """ローディング判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_loading(frame)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("loading_1.png", False),
        ("power_off.png", True),
        ("battle_result_1.png", True),
    ],
)
async def test_detect_loading_end(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """ローディング判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_loading_end(frame)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("battle_result_1.png", True),
        # ("battle_result_2.png", True), # 未対応
        ("battle_result_3.png", False),
        ("battle_result_4.png", False),
    ],
)
async def test_detect_battle_result(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """バトル終了画面判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.detect_session_result(frame, GameMode.BATTLE)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, expected",
    [
        (
            "battle_result_1.png",
            BattleResult(
                Match("Xマッチ"),
                Rule("ガチホコ"),
                Stage("デカライン高架下"),
                3,
                2,
                1,
            ),
        ),
        # (     # 表彰なしは未対応
        #     "battle_result_2.png",
        #     BattleResult(
        #         Match("Xマッチ"),
        #         Rule("ガチホコ"),
        #         Stage("マサバ海峡大橋"),
        #         0,
        #         3,
        #         0,
        #     ),
        # ),
        (
            "battle_result_3.png",
            BattleResult(
                Match("Xマッチ"),
                Rule("ガチホコ"),
                Stage("マサバ海峡大橋"),
                5,
                6,
                1,
            ),
        ),
        (
            "battle_result_4.png",
            BattleResult(
                Match("Xマッチ"),
                Rule("ガチホコ"),
                Stage("マサバ海峡大橋"),
                10,
                6,
                3,
            ),
        ),
        (
            "battle_result_5.png",
            BattleResult(
                Match("レギュラーマッチ"),
                Rule("ナワバリ"),
                Stage("コンブトラック"),
                4,
                4,
                1,
            ),
        ),
        (
            "battle_result_6.png",
            BattleResult(
                Match("トリカラマッチ"),
                Rule("トリカラ"),
                Stage("マンタマリア号"),
                6,
                2,
                3,
            ),
        ),
        (
            "battle_result_7.png",
            BattleResult(
                Match("Xマッチ"),
                Rule("ガチホコ"),
                Stage("ナンプラー遺跡"),
                11,
                7,
                3,
            ),
        ),
    ],
)
async def test_extract_session_result(
    analyzer: FrameAnalyzer,
    load_image: Callable[[str], np.ndarray],
    filename: str,
    expected: bool,
) -> None:
    """バトル終了画面判定の結果を確認する。"""
    frame = load_image(filename)
    result = await analyzer.extract_session_result(frame, GameMode.BATTLE)
    assert result == expected


if __name__ == "__main__":
    import asyncio

    analyzer_ = create_analyzer()
    filename = "battle_result_3.png"
    expected = BattleResult(
        Match("Xマッチ"),
        Rule("ガチホコ"),
        Stage("マサバ海峡大橋"),
        5,
        6,
        1,
    )
    image_path = TEMPLATE_DIR / filename
    frame = as_frame(cv2.imread(str(image_path)))
    asyncio.run(analyzer_.detect_session_result(frame, GameMode.BATTLE))
    result = asyncio.run(
        analyzer_.extract_session_result(frame, GameMode.BATTLE)
    )
    print(result == expected)
    print(result)
