from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from splat_replay.domain.config import ImageMatchingSettings
from splat_replay.infrastructure.adapters.weapon_detection.constants import (
    UNKNOWN_WEAPON_LABEL,
)
from splat_replay.infrastructure.adapters.weapon_detection import constants
from splat_replay.infrastructure.adapters.weapon_detection.recognizer import (
    WeaponRecognitionAdapter,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "weapon_detection"
VISIBLE_FIXTURE_DIR = FIXTURE_DIR / "weapon_icons_visible"
MATCHING_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "image_matching.yaml"
)

EXPECTED_WEAPONS_BY_SAMPLE: dict[str, dict[str, str]] = {
    "weapon_icons_visible_01": {
        "ally_1": "スパッタリーOWL",
        "ally_2": "52ガロン",
        "ally_3": "ノヴァブラスターネオ",
        "ally_4": "スプラシューターコラボ",
        "enemy_1": "スプラシューターコラボ",
        "enemy_2": "ジムワイパー・ヒュー",
        "enemy_3": "オーダースピナーレプリカ",
        "enemy_4": "プロモデラーMG",
    },
    "weapon_icons_visible_02": {
        "ally_1": "スパッタリーOWL",
        "ally_2": "オーダースピナーレプリカ",
        "ally_3": "スクリュースロッシャー",
        "ally_4": "トライストリンガーコラボ",
        "enemy_1": "エクスプロッシャーカスタム",
        "enemy_2": "シャープマーカーネオ",
        "enemy_3": "フルイドV",
        "enemy_4": "ノーチラス79",
    },
    "weapon_icons_visible_03": {
        "ally_1": "スプラシューター煌",
        "ally_2": "わかばシューター",
        "ally_3": "シャープマーカー",
        "ally_4": "スプラシューターコラボ",
        "enemy_1": "スパッタリー・ヒュー",
        "enemy_2": "14式竹筒銃・甲",
        "enemy_3": "パブロ",
        "enemy_4": "フィンセント・ヒュー",
    },
    "weapon_icons_visible_04": {
        "ally_1": "リッター4K",
        "ally_2": "カーボンローラーデコ",
        "ally_3": "スパッタリー・ヒュー",
        "ally_4": "デュアルスイーパー",
        "enemy_1": "パブロ・ヒュー",
        "enemy_2": "リッター4K",
        "enemy_3": "スプラマニューバーコラボ",
        "enemy_4": "ケルビン525",
    },
    "weapon_icons_visible_05": {
        "ally_1": "スプラマニューバーコラボ",
        "ally_2": "ヒッセン・ヒュー",
        "ally_3": "わかばシューター",
        "ally_4": "スパッタリー・ヒュー",
        "enemy_1": "パブロ",
        "enemy_2": "スプラシューターコラボ",
        "enemy_3": "ハイドラント",
        "enemy_4": "エクスプロッシャーカスタム",
    },
    "weapon_icons_visible_06": {
        "ally_1": "スパッタリーOWL",
        "ally_2": "4Kスコープ",
        "ally_3": "プロモデラーMG",
        "ally_4": "モップリンD",
        "enemy_1": "4Kスコープ",
        "enemy_2": "イグザミナー",
        "enemy_3": "スプラシューター",
        "enemy_4": "ボールドマーカー",
    },
    "weapon_icons_visible_07": {
        "ally_1": "オーバーフロッシャー",
        "ally_2": "スパッタリーOWL",
        "ally_3": "プライムシューターFRZN",
        "ally_4": "ジムワイパー",
        "enemy_1": "ノーチラス79",
        "enemy_2": "オーダーワイパーレプリカ",
        "enemy_3": "S-BLAST91",
        "enemy_4": "スプラマニューバーコラボ",
    },
    "weapon_icons_visible_08": {
        "ally_1": "フィンセント・ヒュー",
        "ally_2": "ノーチラス47",
        "ally_3": "オーダーブラシレプリカ",
        "ally_4": "スパッタリーOWL",
        "enemy_1": "シャープマーカー",
        "enemy_2": "パブロ",
        "enemy_3": "バケットスロッシャー",
        "enemy_4": "ホクサイ・ヒュー",
    },
    "weapon_icons_visible_09": {
        "ally_1": "リッター4K",
        "ally_2": "LACT-450MILK",
        "ally_3": "シャープマーカー",
        "ally_4": "カーボンローラーデコ",
        "enemy_1": "N-ZAP89",
        "enemy_2": "クアッドホッパーブラック",
        "enemy_3": "R-PEN5H",
        "enemy_4": "プロモデラーRG",
    },
    "weapon_icons_visible_10": {
        "ally_1": "ハイドラント",
        "ally_2": "シャープマーカー",
        "ally_3": "ボールドマーカー",
        "ally_4": "プロモデラーRG",
        "enemy_1": "ヒーローシューターレプリカ",
        "enemy_2": "プロモデラーRG",
        "enemy_3": "スプラローラー",
        "enemy_4": "バレルスピナー",
    },
    "weapon_icons_visible_11": {
        "ally_1": "ヒーローシューターレプリカ",
        "ally_2": "LACT-450MILK",
        "ally_3": "シャープマーカー",
        "ally_4": "プライムシューター",
        "enemy_1": "シャープマーカーネオ",
        "enemy_2": "N-ZAP89",
        "enemy_3": "スプラシューターコラボ",
        "enemy_4": "リッター4K",
    },
    "weapon_icons_visible_12": {
        "ally_1": "プロモデラーMG",
        "ally_2": "シャープマーカー",
        "ally_3": "プロモデラーRG",
        "ally_4": "ヴァリアブルローラー",
        "enemy_1": "リッター4K",
        "enemy_2": "プロモデラーRG",
        "enemy_3": "ホクサイ・ヒュー",
        "enemy_4": "ボトルガイザーフォイル",
    },
    "weapon_icons_visible_13": {
        "ally_1": "シャープマーカー",
        "ally_2": "スペースシューター",
        "ally_3": "キャンピングシェルターCREM",
        "ally_4": "ボールドマーカー",
        "enemy_1": "ボールドマーカー",
        "enemy_2": "クーゲルシュライバー",
        "enemy_3": "フィンセント・ヒュー",
        "enemy_4": "オーバーフロッシャー",
    },
    "weapon_icons_visible_14": {
        "ally_1": "スプラスピナーPYTN",
        "ally_2": "リッター4Kカスタム",
        "ally_3": "スプラシューター煌",
        "ally_4": "スパッタリーOWL",
        "enemy_1": "リッター4Kカスタム",
        "enemy_2": "オーダーローラーレプリカ",
        "enemy_3": "スプラシューター煌",
        "enemy_4": "LACT-450MILK",
    },
    "weapon_icons_visible_15": {
        "ally_1": "もみじシューター",
        "ally_2": "Rブラスターエリートデコ",
        "ally_3": "スパッタリー・ヒュー",
        "ally_4": "スプラシューター",
        "enemy_1": "もみじシューター",
        "enemy_2": "クラッシュブラスター",
        "enemy_3": "スプラマニューバーコラボ",
        "enemy_4": "トライストリンガー",
    },
    "weapon_icons_visible_16": {
        "ally_1": "プロモデラーRG",
        "ally_2": "オーバーフロッシャー",
        "ally_3": "シャープマーカー",
        "ally_4": "スペースシューター",
        "enemy_1": "ボールドマーカーネオ",
        "enemy_2": "N-ZAP89",
        "enemy_3": "N-ZAP89",
        "enemy_4": "プロモデラーMG",
    },
}


class _TestLogger:
    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        return None

    def error(self, event: str, **kw: object) -> None:
        return None

    def exception(self, event: str, **kw: object) -> None:
        return None


@pytest.fixture(scope="module")
def recognizer() -> WeaponRecognitionAdapter:
    settings = ImageMatchingSettings.load_from_yaml(MATCHING_CONFIG_PATH)
    return WeaponRecognitionAdapter(settings=settings, logger=_TestLogger())


def _load_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path))
    assert image is not None, f"failed to load: {path}"
    return image


def _to_expected_order(slots: dict[str, str]) -> tuple[list[str], list[str]]:
    allies = [slots[f"ally_{idx}"] for idx in range(1, 5)]
    enemies = [slots[f"enemy_{idx}"] for idx in range(1, 5)]
    return allies, enemies


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    [f"weapon_icons_visible_{index:02d}.png" for index in range(1, 17)],
)
async def test_detect_weapon_display_true(
    recognizer: WeaponRecognitionAdapter, filename: str
) -> None:
    frame = _load_image(VISIBLE_FIXTURE_DIR / filename)
    assert await recognizer.detect_weapon_display(frame) is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    [
        "no_weapon_icons_screen.png",
        "no_weapon_icons_screen_2.png",
        "no_weapon_icons_screen_3.png",
        "no_weapon_icons_screen_4.png",
    ],
)
async def test_detect_weapon_display_false(
    recognizer: WeaponRecognitionAdapter, filename: str
) -> None:
    frame = _load_image(FIXTURE_DIR / filename)
    assert await recognizer.detect_weapon_display(frame) is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sample_id",
    [f"weapon_icons_visible_{index:02d}" for index in range(1, 17)],
)
async def test_recognize_weapons_detects_all_slots(
    recognizer: WeaponRecognitionAdapter, sample_id: str
) -> None:
    frame = _load_image(VISIBLE_FIXTURE_DIR / f"{sample_id}.png")
    result = await recognizer.recognize_weapons(
        frame,
        save_unmatched_report=False,
    )

    assert len(result.allies) == 4
    assert len(result.enemies) == 4
    assert len(result.slot_results) == 8

    predicted = [slot.predicted_weapon for slot in result.slot_results]
    assert list(result.allies) + list(result.enemies) == predicted
    for label in predicted:
        assert label != ""


@pytest.mark.asyncio
async def test_recognize_weapons_uses_template_threshold_from_config() -> None:
    settings = ImageMatchingSettings.load_from_yaml(MATCHING_CONFIG_PATH)
    template_keys = settings.matcher_groups.get(
        constants.WEAPON_TEMPLATE_MATCHER_GROUP, []
    )
    assert template_keys
    for key in template_keys:
        settings.matchers[key].threshold = 1.01

    strict_recognizer = WeaponRecognitionAdapter(
        settings=settings, logger=_TestLogger()
    )
    frame = _load_image(VISIBLE_FIXTURE_DIR / "weapon_icons_visible_01.png")
    result = await strict_recognizer.recognize_weapons(
        frame,
        save_unmatched_report=False,
    )

    assert list(result.allies) == [UNKNOWN_WEAPON_LABEL] * 4
    assert list(result.enemies) == [UNKNOWN_WEAPON_LABEL] * 4


@pytest.mark.asyncio
async def test_recognize_weapons_outputs_unmatched_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(constants, "UNMATCHED_OUTPUT_DIR", tmp_path)
    settings = ImageMatchingSettings.load_from_yaml(MATCHING_CONFIG_PATH)
    template_keys = settings.matcher_groups.get(
        constants.WEAPON_TEMPLATE_MATCHER_GROUP, []
    )
    assert template_keys
    for key in template_keys:
        settings.matchers[key].threshold = 1.01

    recognizer = WeaponRecognitionAdapter(
        settings=settings, logger=_TestLogger()
    )
    frame = _load_image(VISIBLE_FIXTURE_DIR / "weapon_icons_visible_16.png")
    result = await recognizer.recognize_weapons(frame)

    assert list(result.allies) == [UNKNOWN_WEAPON_LABEL] * 4
    assert list(result.enemies) == [UNKNOWN_WEAPON_LABEL] * 4
    assert result.unmatched_output_dir is not None

    summary_path = Path(result.unmatched_output_dir) / "summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["unmatched_count"] == 8
    assert len(summary["rows"]) == 8
    for row in summary["rows"]:
        assert row["threshold"] == 1.01
        if row["top1"] is not None:
            assert row["top1"]["threshold"] == 1.01
        if row["top2"] is not None:
            assert row["top2"]["threshold"] == 1.01
        if row["top3"] is not None:
            assert row["top3"]["threshold"] == 1.01
        assert Path(row["saved_weapon_only"]).exists()
        assert Path(row["saved_mask"]).exists()
        assert "saved_template" not in row
        assert "saved_template_mask" not in row
