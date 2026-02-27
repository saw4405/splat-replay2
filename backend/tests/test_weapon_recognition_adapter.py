from __future__ import annotations

import asyncio
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from splat_replay.domain.config import ImageMatchingSettings
from splat_replay.infrastructure.adapters.weapon_detection import constants
from splat_replay.infrastructure.adapters.weapon_detection.constants import (
    UNKNOWN_WEAPON_LABEL,
)
from splat_replay.infrastructure.adapters.weapon_detection.recognizer import (
    WeaponRecognitionAdapter,
)
from splat_replay.infrastructure.adapters.weapon_detection.team_color import (
    TeamColorScreenMetrics,
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


class _SpyLogger(_TestLogger):
    def __init__(self) -> None:
        self.debug_calls: list[tuple[str, dict[str, object]]] = []

    def debug(self, event: str, **kw: object) -> None:
        self.debug_calls.append((event, kw))


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
async def test_detect_weapon_display_false_when_outline_matched_slots_is_three(
    recognizer: WeaponRecognitionAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _load_image(VISIBLE_FIXTURE_DIR / "weapon_icons_visible_01.png")
    metrics = TeamColorScreenMetrics(
        allies_max_distance=0.0,
        enemies_max_distance=0.0,
        teams_min_distance=999.0,
    )
    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer.detect_weapon_display_screen",
        lambda _: (True, metrics),
    )
    monkeypatch.setattr(recognizer, "_get_outline_model_masks", lambda: {})
    iou_by_slot = {slot: 0.0 for slot in constants.SLOT_ORDER}
    for slot in constants.SLOT_ORDER[:3]:
        iou_by_slot[slot] = constants.WEAPON_DISPLAY_OUTLINE_MIN_IOU
    monkeypatch.setattr(
        recognizer,
        "_count_outline_matched_slots",
        lambda *,
        slot_images,
        model_masks,
        cancel_generation=None,
        max_shift=None: (  # noqa: E501
            3,
            iou_by_slot,
            8,
        ),
    )

    assert await recognizer.detect_weapon_display(frame) is False


@pytest.mark.asyncio
async def test_detect_weapon_display_true_when_outline_matched_slots_is_four(
    recognizer: WeaponRecognitionAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _load_image(VISIBLE_FIXTURE_DIR / "weapon_icons_visible_01.png")
    metrics = TeamColorScreenMetrics(
        allies_max_distance=0.0,
        enemies_max_distance=0.0,
        teams_min_distance=999.0,
    )
    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer.detect_weapon_display_screen",
        lambda _: (True, metrics),
    )
    monkeypatch.setattr(recognizer, "_get_outline_model_masks", lambda: {})
    iou_by_slot = {slot: 0.0 for slot in constants.SLOT_ORDER}
    for slot in constants.SLOT_ORDER[:4]:
        iou_by_slot[slot] = constants.WEAPON_DISPLAY_OUTLINE_MIN_IOU
    monkeypatch.setattr(
        recognizer,
        "_count_outline_matched_slots",
        lambda *,
        slot_images,
        model_masks,
        cancel_generation=None,
        max_shift=None: (  # noqa: E501
            4,
            iou_by_slot,
            4,
        ),
    )

    assert await recognizer.detect_weapon_display(frame) is True


@pytest.mark.asyncio
async def test_detect_weapon_display_uses_fast_path_without_fallback_when_fast_passes(
    recognizer: WeaponRecognitionAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _load_image(VISIBLE_FIXTURE_DIR / "weapon_icons_visible_01.png")
    metrics = TeamColorScreenMetrics(
        allies_max_distance=0.0,
        enemies_max_distance=0.0,
        teams_min_distance=999.0,
    )
    spy_logger = _SpyLogger()
    recognizer._logger = spy_logger
    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer.detect_weapon_display_screen",
        lambda _: (True, metrics),
    )
    monkeypatch.setattr(recognizer, "_get_outline_model_masks", lambda: {})
    iou_by_slot = {slot: 0.0 for slot in constants.SLOT_ORDER}
    for slot in constants.SLOT_ORDER[:4]:
        iou_by_slot[slot] = constants.WEAPON_DISPLAY_OUTLINE_MIN_IOU

    shifts: list[int | None] = []

    def _count_outline_matched_slots(
        *,
        slot_images: dict[str, np.ndarray],
        model_masks: dict[str, np.ndarray],
        cancel_generation: int | None = None,
        max_shift: int | None = None,
    ) -> tuple[int, dict[str, float], int]:
        _ = slot_images
        _ = model_masks
        _ = cancel_generation
        shifts.append(max_shift)
        return (4, iou_by_slot, 4)

    monkeypatch.setattr(
        recognizer,
        "_count_outline_matched_slots",
        _count_outline_matched_slots,
    )

    assert await recognizer.detect_weapon_display(frame) is True
    assert shifts == [constants.OUTLINE_ALIGN_FAST_MAX_SHIFT]
    assert spy_logger.debug_calls
    _, fields = spy_logger.debug_calls[-1]
    assert fields["fallback_used"] is False
    assert fields["processed_slots"] == 4
    assert fields["fast_shift"] == constants.OUTLINE_ALIGN_FAST_MAX_SHIFT


@pytest.mark.asyncio
async def test_detect_weapon_display_runs_precise_fallback_when_fast_pass_fails(
    recognizer: WeaponRecognitionAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _load_image(VISIBLE_FIXTURE_DIR / "weapon_icons_visible_01.png")
    metrics = TeamColorScreenMetrics(
        allies_max_distance=0.0,
        enemies_max_distance=0.0,
        teams_min_distance=999.0,
    )
    spy_logger = _SpyLogger()
    recognizer._logger = spy_logger
    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer.detect_weapon_display_screen",
        lambda _: (True, metrics),
    )
    monkeypatch.setattr(recognizer, "_get_outline_model_masks", lambda: {})

    fast_iou = {slot: 0.0 for slot in constants.SLOT_ORDER}
    for slot in constants.SLOT_ORDER[:3]:
        fast_iou[slot] = constants.WEAPON_DISPLAY_OUTLINE_MIN_IOU
    precise_iou = {slot: 0.0 for slot in constants.SLOT_ORDER}
    for slot in constants.SLOT_ORDER[:4]:
        precise_iou[slot] = constants.WEAPON_DISPLAY_OUTLINE_MIN_IOU

    shifts: list[int | None] = []

    def _count_outline_matched_slots(
        *,
        slot_images: dict[str, np.ndarray],
        model_masks: dict[str, np.ndarray],
        cancel_generation: int | None = None,
        max_shift: int | None = None,
    ) -> tuple[int, dict[str, float], int]:
        _ = slot_images
        _ = model_masks
        _ = cancel_generation
        shifts.append(max_shift)
        if max_shift == constants.OUTLINE_ALIGN_FAST_MAX_SHIFT:
            return (3, fast_iou, 8)
        return (4, precise_iou, 5)

    monkeypatch.setattr(
        recognizer,
        "_count_outline_matched_slots",
        _count_outline_matched_slots,
    )

    assert await recognizer.detect_weapon_display(frame) is True
    assert shifts == [
        constants.OUTLINE_ALIGN_FAST_MAX_SHIFT,
        constants.OUTLINE_ALIGN_MAX_SHIFT,
    ]
    assert spy_logger.debug_calls
    _, fields = spy_logger.debug_calls[-1]
    assert fields["fallback_used"] is True
    assert fields["processed_slots"] == 5
    assert fields["fast_shift"] == constants.OUTLINE_ALIGN_FAST_MAX_SHIFT


@pytest.mark.asyncio
async def test_count_outline_matched_slots_early_returns_at_threshold(
    recognizer: WeaponRecognitionAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slot_images = {
        slot: np.zeros((8, 8, 3), dtype=np.uint8)
        for slot in constants.SLOT_ORDER
    }
    calls = 0

    def _detect_slot_team_region(_: np.ndarray) -> np.ndarray:
        nonlocal calls
        calls += 1
        return np.ones((8, 8), dtype=np.uint8)

    def _infer_species_and_mask(
        *,
        detected_mask: np.ndarray,
        model_masks: dict[str, np.ndarray],
        max_shift: int | None = None,
    ) -> tuple[str, np.ndarray]:
        _ = model_masks
        _ = max_shift
        return "ika", detected_mask

    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer.detect_slot_team_region",
        _detect_slot_team_region,
    )
    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer.outline_models.infer_species_and_mask",
        _infer_species_and_mask,
    )

    matched_slots, iou_by_slot, processed_slots = (
        recognizer._count_outline_matched_slots(
            slot_images=slot_images,
            model_masks={},
            max_shift=constants.OUTLINE_ALIGN_FAST_MAX_SHIFT,
        )
    )

    assert matched_slots == constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
    assert (
        processed_slots == constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
    )
    assert calls == constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
    for slot in constants.SLOT_ORDER[:4]:
        assert iou_by_slot[slot] >= constants.WEAPON_DISPLAY_OUTLINE_MIN_IOU
    for slot in constants.SLOT_ORDER[4:]:
        assert iou_by_slot[slot] == 0.0


@pytest.mark.asyncio
async def test_detect_weapon_display_raises_when_outline_model_loading_failed(
    recognizer: WeaponRecognitionAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _load_image(VISIBLE_FIXTURE_DIR / "weapon_icons_visible_01.png")
    metrics = TeamColorScreenMetrics(
        allies_max_distance=0.0,
        enemies_max_distance=0.0,
        teams_min_distance=999.0,
    )
    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer.detect_weapon_display_screen",
        lambda _: (True, metrics),
    )

    def _raise_load_error() -> dict[str, np.ndarray]:
        raise RuntimeError("failed to load outline models")

    monkeypatch.setattr(
        recognizer, "_get_outline_model_masks", _raise_load_error
    )

    with pytest.raises(RuntimeError, match="failed to load outline models"):
        await recognizer.detect_weapon_display(frame)


@pytest.mark.asyncio
async def test_recognize_weapons_stops_calculation_after_cancel_request(
    recognizer: WeaponRecognitionAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _load_image(VISIBLE_FIXTURE_DIR / "weapon_icons_visible_01.png")
    score_started = asyncio.Event()

    async def _slow_score(
        query_padded_bgr: np.ndarray,
        *,
        cancel_check: object = None,
    ) -> float:
        _ = query_padded_bgr
        score_started.set()
        while True:
            if callable(cancel_check) and cancel_check():
                raise asyncio.CancelledError("cancelled by test")
            await asyncio.sleep(0.001)

    for template_sources in recognizer._template_sources_by_weapon.values():
        for source in template_sources:
            monkeypatch.setattr(source.matcher, "score", _slow_score)

    task = asyncio.create_task(
        recognizer.recognize_weapons(
            frame,
            save_unmatched_report=False,
        )
    )
    await asyncio.wait_for(score_started.wait(), timeout=1.0)

    recognizer.request_cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)


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
async def test_recognize_weapons_accepts_non_display_frame_with_strict_threshold() -> (
    None
):
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
    frame = _load_image(FIXTURE_DIR / "no_weapon_icons_screen.png")
    result = await strict_recognizer.recognize_weapons(
        frame,
        save_unmatched_report=False,
    )

    assert list(result.allies) == [UNKNOWN_WEAPON_LABEL] * 4
    assert list(result.enemies) == [UNKNOWN_WEAPON_LABEL] * 4


@pytest.mark.asyncio
async def test_recognize_weapons_skips_report_queries_when_report_disabled(
    recognizer: WeaponRecognitionAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _load_image(VISIBLE_FIXTURE_DIR / "weapon_icons_visible_01.png")

    def _unexpected_ensure_outline_models(
        *, assets_dir: Path, logger: object
    ) -> dict[str, np.ndarray]:
        raise AssertionError(
            "save_unmatched_report=False では outline モデル読み込みは不要です"
        )

    def _unexpected_build_query_slot_data(
        *,
        slot_images: dict[str, np.ndarray],
        model_masks: dict[str, np.ndarray],
    ) -> dict[str, object]:
        raise AssertionError(
            "save_unmatched_report=False では QuerySlotData 生成は不要です"
        )

    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer.outline_models.ensure_outline_models",
        _unexpected_ensure_outline_models,
    )
    monkeypatch.setattr(
        "splat_replay.infrastructure.adapters.weapon_detection.recognizer.build_query_slot_data",
        _unexpected_build_query_slot_data,
    )

    result = await recognizer.recognize_weapons(
        frame,
        save_unmatched_report=False,
    )

    assert len(result.slot_results) == 8
    assert result.unmatched_output_dir is None


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
        assert row["predicted_score"] is not None
        assert len(row["top_candidates"]) == 3
        for candidate in row["top_candidates"]:
            assert candidate["threshold"] == 1.01
        assert "top1" not in row
        assert "top2" not in row
        assert "top3" not in row
        assert Path(row["saved_slot"]).exists()
        assert Path(row["saved_weapon_only"]).exists()
        assert Path(row["saved_mask"]).exists()
        assert "saved_template" not in row
        assert "saved_template_mask" not in row
        top1_weapon = row["top_candidates"][0]["weapon"]
        expected_weapon = constants.INVALID_FILENAME_CHARS_PATTERN.sub(
            "_", top1_weapon
        )
        assert expected_weapon in Path(row["saved_slot"]).name
        assert expected_weapon in Path(row["saved_weapon_only"]).name
        assert expected_weapon in Path(row["saved_mask"]).name


@pytest.mark.asyncio
async def test_recognize_weapons_partial_report_counts_only_target_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """レポート出力時は、target_slotsに関わらず全8スロット分を出力する。"""
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
    result = await recognizer.recognize_weapons(
        frame,
        save_unmatched_report=True,
        target_slots={"ally_1"},
    )

    assert result.unmatched_output_dir is not None
    summary_path = Path(result.unmatched_output_dir) / "summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    # レポートは全8スロット分を出力
    assert summary["unmatched_count"] == 8
    assert len(summary["rows"]) == 8
    # target_slotsに含まれるally_1のみ判別され、他は未判別
    ally_1_row = next(r for r in summary["rows"] if r["slot"] == "ally_1")
    assert ally_1_row["predicted_weapon"] == UNKNOWN_WEAPON_LABEL
    assert ally_1_row["is_unmatched"] is True
