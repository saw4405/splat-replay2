"""ブキ表示検出・判別アダプタ。"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from functools import cmp_to_key
from pathlib import Path
from typing import cast

import cv2
import numpy as np
from splat_replay.application.interfaces import (
    LoggerPort,
    WeaponCandidateScore,
    WeaponRecognitionPort,
    WeaponRecognitionResult,
    WeaponSlotResult,
)
from splat_replay.domain.config import ImageMatchingSettings, MatcherConfig
from splat_replay.domain.models import Frame
from splat_replay.infrastructure.filesystem import ASSETS_DIR
from splat_replay.infrastructure.matchers import TemplateMatcher

from . import (
    constants,
    labeling_variant_bank,
    outline_models,
    unmatched_report,
)
from .query_builder import (
    QuerySlotData,
    build_padded_gray_by_slot,
    build_query_slot_data,
    crop_slot_images,
)
from .team_color import detect_slot_team_region, detect_weapon_display_screen


def _to_four_tuple(items: list[str]) -> tuple[str, str, str, str]:
    """4要素のリストを固定長タプルに変換する。型チェッカー用のヘルパー。"""
    if len(items) != 4:
        raise ValueError(f"Expected exactly 4 items, got {len(items)}")
    return (items[0], items[1], items[2], items[3])


@dataclass(frozen=True)
class _TemplateSource:
    matcher: TemplateMatcher
    template_path: Path
    mask_path: Path
    threshold: float


@dataclass(frozen=True)
class _RankedCandidate:
    weapon: str
    score: float
    template_source: _TemplateSource | None
    template_threshold: float


@dataclass(frozen=True)
class _SlotSignalMetrics:
    edge_ratio: float
    team_edge_ratio: float


class WeaponRecognitionAdapter(WeaponRecognitionPort):
    """TemplateMatcher を用いたブキ判別アダプタ。"""

    def __init__(
        self,
        settings: ImageMatchingSettings,
        logger: LoggerPort,
        assets_dir: Path = ASSETS_DIR,
    ) -> None:
        self._settings = settings
        self._logger = logger
        self._assets_dir = assets_dir
        (
            self._template_sources_by_weapon,
            self._variant_template_sources_by_weapon,
        ) = self._load_template_sources()
        self._template_sources_with_variant_by_weapon = (
            self._merge_template_sources(
                base=self._template_sources_by_weapon,
                addition=self._variant_template_sources_by_weapon,
            )
        )
        self._labeling_variant_sources_by_weapon = (
            self._load_labeling_variant_sources()
        )
        self._matching_assets_dir = self._resolve_matching_assets_dir()
        self._outline_model_masks: dict[str, np.ndarray] | None = None
        self._cancel_lock = threading.Lock()
        self._cancel_generation = 0

    def request_cancel(self) -> None:
        """進行中の判別処理を中断する。"""
        with self._cancel_lock:
            self._cancel_generation += 1

    def _capture_cancel_generation(self) -> int:
        with self._cancel_lock:
            return self._cancel_generation

    def _is_cancelled(self, cancel_generation: int) -> bool:
        with self._cancel_lock:
            return cancel_generation != self._cancel_generation

    def _ensure_not_cancelled(self, cancel_generation: int) -> None:
        if self._is_cancelled(cancel_generation):
            raise asyncio.CancelledError("weapon recognition cancelled")

    async def detect_weapon_display(self, frame: Frame) -> bool:
        cancel_generation = self._capture_cancel_generation()
        self._ensure_not_cancelled(cancel_generation)
        slot_images = crop_slot_images(frame)
        color_visible, metrics = detect_weapon_display_screen(slot_images)
        outline_matched_slots = 0
        processed_slots = 0
        fallback_used = False
        display_weapon_region_ratio: float | None = None
        matched_slot_team_edge_ratio: float | None = None
        outline_iou_by_slot = {slot: 0.0 for slot in constants.SLOT_ORDER}
        if color_visible:
            model_masks = self._get_outline_model_masks()
            fast_result = self._count_outline_matched_slots(
                slot_images=slot_images,
                model_masks=model_masks,
                cancel_generation=cancel_generation,
                max_shift=constants.OUTLINE_ALIGN_FAST_MAX_SHIFT,
            )
            (
                fast_matched_slots,
                fast_iou_by_slot,
                fast_processed_slots,
                fast_weapon_region_ratio,
            ) = self._unpack_outline_count_result(fast_result)
            # fast path が最小必要数に達していても、4 枠を超えて探索して
            # ようやく成立した場合は片側だけの誤一致の可能性があるため、
            # precise path で再検証する。
            should_run_precise_validation = (
                fast_processed_slots
                > constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
            )
            if (
                fast_matched_slots
                >= constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
                and not should_run_precise_validation
            ):
                outline_matched_slots = fast_matched_slots
                outline_iou_by_slot = fast_iou_by_slot
                processed_slots = fast_processed_slots
                display_weapon_region_ratio = fast_weapon_region_ratio
            else:
                fallback_used = True
                precise_result: (
                    tuple[int, dict[str, float], int, float | None] | None
                ) = None
                if (
                    fast_matched_slots
                    >= constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
                    and should_run_precise_validation
                ):
                    matched_fast_slots = self._extract_outline_matched_slots(
                        fast_iou_by_slot
                    )
                    precise_result = self._count_outline_matched_slots(
                        slot_images=slot_images,
                        model_masks=model_masks,
                        cancel_generation=cancel_generation,
                        max_shift=constants.OUTLINE_ALIGN_MAX_SHIFT,
                        slot_order=matched_fast_slots,
                    )
                    precise_matched_slots, _, _, _ = (
                        self._unpack_outline_count_result(precise_result)
                    )
                    if (
                        precise_matched_slots
                        < constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
                    ):
                        precise_result = None
                if precise_result is None:
                    precise_result = self._count_outline_matched_slots(
                        slot_images=slot_images,
                        model_masks=model_masks,
                        cancel_generation=cancel_generation,
                        max_shift=constants.OUTLINE_ALIGN_MAX_SHIFT,
                    )
                (
                    outline_matched_slots,
                    outline_iou_by_slot,
                    processed_slots,
                    display_weapon_region_ratio,
                ) = self._unpack_outline_count_result(precise_result)
        self._ensure_not_cancelled(cancel_generation)

        weapon_region_ratio_passed = True
        if display_weapon_region_ratio is not None:
            weapon_region_ratio_passed = (
                display_weapon_region_ratio
                >= constants.WEAPON_DISPLAY_MIN_WEAPON_REGION_RATIO
            )
        team_edge_ratio_passed = True
        if (
            outline_matched_slots
            >= constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
        ):
            matched_slot_team_edge_ratio = (
                self._calc_outline_matched_slot_team_edge_ratio(
                    slot_images=slot_images,
                    iou_by_slot=outline_iou_by_slot,
                )
            )
        if matched_slot_team_edge_ratio is not None:
            team_edge_ratio_passed = (
                matched_slot_team_edge_ratio
                <= constants.WEAPON_DISPLAY_MAX_MATCHED_SLOT_TEAM_EDGE_RATIO
            )
        is_visible = (
            color_visible
            and (
                outline_matched_slots
                >= constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
            )
            and weapon_region_ratio_passed
            and team_edge_ratio_passed
        )
        self._logger.debug(
            "ブキ表示判定",
            is_visible=is_visible,
            allies_max_distance=metrics.allies_max_distance,
            enemies_max_distance=metrics.enemies_max_distance,
            teams_min_distance=metrics.teams_min_distance,
            outline_matched_slots=outline_matched_slots,
            processed_slots=processed_slots,
            outline_required_slots=constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS,
            outline_iou_threshold=constants.WEAPON_DISPLAY_OUTLINE_MIN_IOU,
            display_weapon_region_ratio=(
                round(display_weapon_region_ratio, 6)
                if display_weapon_region_ratio is not None
                else None
            ),
            display_weapon_region_ratio_threshold=round(
                constants.WEAPON_DISPLAY_MIN_WEAPON_REGION_RATIO,
                6,
            ),
            display_weapon_region_ratio_passed=(
                weapon_region_ratio_passed
                if display_weapon_region_ratio is not None
                else None
            ),
            matched_slot_team_edge_ratio=(
                round(matched_slot_team_edge_ratio, 6)
                if matched_slot_team_edge_ratio is not None
                else None
            ),
            matched_slot_team_edge_ratio_threshold=round(
                constants.WEAPON_DISPLAY_MAX_MATCHED_SLOT_TEAM_EDGE_RATIO,
                6,
            ),
            matched_slot_team_edge_ratio_passed=(
                team_edge_ratio_passed
                if matched_slot_team_edge_ratio is not None
                else None
            ),
            fast_shift=constants.OUTLINE_ALIGN_FAST_MAX_SHIFT,
            fallback_used=fallback_used,
            outline_iou_by_slot={
                slot: round(iou, 6)
                for slot, iou in outline_iou_by_slot.items()
            },
        )
        return is_visible

    def _get_outline_model_masks(self) -> dict[str, np.ndarray]:
        if self._outline_model_masks is None:
            self._outline_model_masks = outline_models.ensure_outline_models(
                assets_dir=self._matching_assets_dir,
                logger=self._logger,
            )
        return self._outline_model_masks

    @staticmethod
    def _unpack_outline_count_result(
        result: tuple[int, dict[str, float], int]
        | tuple[int, dict[str, float], int, float | None],
    ) -> tuple[int, dict[str, float], int, float | None]:
        if len(result) == 3:
            result3 = cast(tuple[int, dict[str, float], int], result)
            matched_slots, iou_by_slot, processed_slots = result3
            return matched_slots, iou_by_slot, processed_slots, None
        result4 = cast(tuple[int, dict[str, float], int, float | None], result)
        (
            matched_slots,
            iou_by_slot,
            processed_slots,
            display_weapon_region_ratio,
        ) = result4
        return (
            matched_slots,
            iou_by_slot,
            processed_slots,
            display_weapon_region_ratio,
        )

    def _count_outline_matched_slots(
        self,
        *,
        slot_images: dict[str, np.ndarray],
        model_masks: dict[str, np.ndarray],
        cancel_generation: int | None = None,
        max_shift: int | None = None,
        slot_order: tuple[str, ...] | None = None,
    ) -> tuple[int, dict[str, float], int, float | None]:
        if cancel_generation is None:
            cancel_generation = self._capture_cancel_generation()
        if max_shift is None:
            max_shift = constants.OUTLINE_ALIGN_MAX_SHIFT
        if slot_order is None:
            slot_order = constants.SLOT_ORDER
        matched_slots = 0
        processed_slots = 0
        matched_slot_weapon_region_ratios: list[float] = []
        iou_by_slot: dict[str, float] = {
            slot: 0.0 for slot in constants.SLOT_ORDER
        }
        for slot in slot_order:
            self._ensure_not_cancelled(cancel_generation)
            processed_slots += 1
            detected_mask = detect_slot_team_region(slot_images[slot])
            iou = 0.0
            aligned_model_mask: np.ndarray | None = None
            if int(detected_mask.sum()) > 0:
                _, aligned_model_mask = outline_models.infer_species_and_mask(
                    detected_mask=detected_mask,
                    model_masks=model_masks,
                    max_shift=max_shift,
                )
                iou = self._calc_iou(detected_mask, aligned_model_mask)

            iou_by_slot[slot] = iou
            if iou >= constants.WEAPON_DISPLAY_OUTLINE_MIN_IOU:
                matched_slots += 1
                if aligned_model_mask is not None:
                    weapon_region_mask = np.logical_and(
                        aligned_model_mask > 0,
                        detected_mask == 0,
                    )
                    weapon_region_ratio = float(
                        int(weapon_region_mask.sum())
                    ) / float(weapon_region_mask.size)
                    matched_slot_weapon_region_ratios.append(
                        weapon_region_ratio
                    )
                if (
                    matched_slots
                    >= constants.WEAPON_DISPLAY_OUTLINE_MIN_MATCHED_SLOTS
                ):
                    break

        display_weapon_region_ratio: float | None = None
        if matched_slot_weapon_region_ratios:
            display_weapon_region_ratio = float(
                np.mean(matched_slot_weapon_region_ratios)
            )
        return (
            matched_slots,
            iou_by_slot,
            processed_slots,
            display_weapon_region_ratio,
        )

    @staticmethod
    def _extract_outline_matched_slots(
        iou_by_slot: dict[str, float],
    ) -> tuple[str, ...]:
        return tuple(
            slot
            for slot in constants.SLOT_ORDER
            if iou_by_slot[slot] >= constants.WEAPON_DISPLAY_OUTLINE_MIN_IOU
        )

    def _calc_outline_matched_slot_team_edge_ratio(
        self,
        *,
        slot_images: dict[str, np.ndarray],
        iou_by_slot: dict[str, float],
    ) -> float | None:
        matched_slots = self._extract_outline_matched_slots(iou_by_slot)
        if not matched_slots:
            return None
        team_edge_ratios = [
            self._compute_slot_signal_metrics(
                slot_image=slot_images[slot]
            ).team_edge_ratio
            for slot in matched_slots
        ]
        return float(np.mean(team_edge_ratios))

    @staticmethod
    def _calc_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
        intersection = int(np.logical_and(mask_a > 0, mask_b > 0).sum())
        union = int(np.logical_or(mask_a > 0, mask_b > 0).sum())
        if union == 0:
            return 0.0
        return intersection / float(union)

    def _compute_slot_signal_metrics(
        self, *, slot_image: np.ndarray
    ) -> _SlotSignalMetrics:
        gray = cv2.cvtColor(slot_image, cv2.COLOR_BGR2GRAY)
        team_mask = detect_slot_team_region(slot_image) > 0
        edges = cv2.Canny(gray, 80, 160) > 0
        edge_ratio = float(int(edges.sum())) / float(edges.size)
        team_pixel_count = int(team_mask.sum())
        if team_pixel_count <= 0:
            return _SlotSignalMetrics(
                edge_ratio=edge_ratio,
                team_edge_ratio=0.0,
            )
        team_edges = int(np.logical_and(edges, team_mask).sum())
        return _SlotSignalMetrics(
            edge_ratio=edge_ratio,
            team_edge_ratio=team_edges / float(team_pixel_count),
        )

    async def recognize_weapons(
        self,
        frame: Frame,
        save_unmatched_report: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
    ) -> WeaponRecognitionResult:
        cancel_generation = self._capture_cancel_generation()
        self._ensure_not_cancelled(cancel_generation)
        if not self._template_sources_by_weapon:
            raise FileNotFoundError(
                "ブキテンプレートが設定されていません。"
                f" matcher_group={constants.WEAPON_TEMPLATE_MATCHER_GROUP}"
            )

        slot_images = crop_slot_images(frame)
        query_padded_gray_by_slot = build_padded_gray_by_slot(
            slot_images=slot_images,
        )
        # レポート出力時は全8スロット分のquery_dataを用意
        query_data_by_slot: dict[str, QuerySlotData] | None = None
        if save_unmatched_report:
            model_masks = outline_models.ensure_outline_models(
                assets_dir=self._matching_assets_dir,
                logger=self._logger,
            )
            self._ensure_not_cancelled(cancel_generation)
            query_data_by_slot = build_query_slot_data(
                slot_images=slot_images,
                model_masks=model_masks,
            )

        slot_results: dict[str, WeaponSlotResult] = {}
        slot_debug_candidates_by_slot: dict[
            str, tuple[unmatched_report.SlotDebugCandidate, ...]
        ] = {}
        for slot in constants.SLOT_ORDER:
            self._ensure_not_cancelled(cancel_generation)
            # target_slotsに含まれないスロットは既存結果を使用（再判別しない）
            if target_slots is not None and slot not in target_slots:
                # 既存結果があれば使用、なければUNKNOWN
                if previous_results is not None and slot in previous_results:
                    slot_results[slot] = previous_results[slot]
                    # 既存結果のデバッグ情報を設定（レポート出力用）
                    if save_unmatched_report:
                        # 既存結果のtop_candidatesから直接threshold取得
                        slot_debug_candidates_by_slot[slot] = tuple(
                            unmatched_report.SlotDebugCandidate(
                                weapon=cand.weapon,
                                score=cand.score,
                                threshold=cand.threshold,
                            )
                            for cand in previous_results[slot].top_candidates
                        )
                else:
                    slot_results[slot] = WeaponSlotResult(
                        slot=slot,
                        predicted_weapon=constants.UNKNOWN_WEAPON_LABEL,
                        is_unmatched=True,
                        top_candidates=(),
                        detected_score=None,
                    )
                    if save_unmatched_report:
                        slot_debug_candidates_by_slot[slot] = ()
                continue
            # target_slotsに含まれるスロットのみ再判別
            slot_signal_metrics = self._compute_slot_signal_metrics(
                slot_image=slot_images[slot]
            )
            slot_result, slot_debug_candidates = await self._predict_slot(
                slot=slot,
                query_padded_gray=query_padded_gray_by_slot[slot],
                cancel_generation=cancel_generation,
                slot_signal_metrics=slot_signal_metrics,
            )
            slot_results[slot] = slot_result
            if save_unmatched_report:
                slot_debug_candidates_by_slot[slot] = slot_debug_candidates

        allies = _to_four_tuple(
            [
                slot_results[slot].predicted_weapon
                for slot in constants.ALLY_SLOTS
            ]
        )
        enemies = _to_four_tuple(
            [
                slot_results[slot].predicted_weapon
                for slot in constants.ENEMY_SLOTS
            ]
        )
        unmatched_output_dir: str | None = None
        if save_unmatched_report:
            self._ensure_not_cancelled(cancel_generation)
            assert query_data_by_slot is not None
            unmatched_output_dir = unmatched_report.save_unmatched_slots(
                frame=frame,
                query_data_by_slot=query_data_by_slot,
                slot_results=slot_results,
                slot_debug_candidates_by_slot=slot_debug_candidates_by_slot,
                target_slots=target_slots,
            )
            self._logger.info(
                "ブキ判別レポートを保存",
                output_dir=unmatched_output_dir,
            )

        return WeaponRecognitionResult(
            allies=allies,
            enemies=enemies,
            slot_results=tuple(
                slot_results[slot] for slot in constants.SLOT_ORDER
            ),
            unmatched_output_dir=unmatched_output_dir,
        )

    async def _predict_slot(
        self,
        *,
        slot: str,
        query_padded_gray: np.ndarray,
        cancel_generation: int,
        slot_signal_metrics: _SlotSignalMetrics | None = None,
    ) -> tuple[
        WeaponSlotResult,
        tuple[unmatched_report.SlotDebugCandidate, ...],
    ]:
        low_signal_forced_unknown = self._is_low_signal_slot(
            slot_signal_metrics=slot_signal_metrics
        )
        ranked = await self._rank_weapon_candidates(
            query_padded_gray,
            cancel_generation=cancel_generation,
        )
        self._ensure_not_cancelled(cancel_generation)
        labeling_variant_rerank_attempted = False
        labeling_variant_rerank_applied = False
        if self._labeling_variant_sources_by_weapon:
            labeling_variant_rerank_attempted = True
            (
                ranked,
                labeling_variant_rerank_applied,
            ) = await self._rerank_top_candidates_with_labeling_variants(
                ranked=ranked,
                query_padded_gray=query_padded_gray,
                cancel_generation=cancel_generation,
            )
            self._ensure_not_cancelled(cancel_generation)
        ranked_before_pair_variant_rerank = list(ranked)
        pair_variant_rerank_attempted = False
        pair_variant_rerank_applied = False
        pair_variant_rerank_weapons: tuple[str, str] | None = None
        pair_variant_rerank_max_score_gap: float | None = None
        pair_variant_rerank_target = self._resolve_pair_variant_rerank_target(
            ranked
        )
        if pair_variant_rerank_target is not None:
            pair_variant_rerank_attempted = True
            pair_variant_rerank_weapons = pair_variant_rerank_target
            pair_variant_rerank_max_score_gap = (
                self._resolve_pair_variant_rerank_max_score_gap(
                    pair_variant_rerank_target
                )
            )
            (
                ranked,
                pair_variant_rerank_applied,
            ) = await self._rerank_specific_weapons_with_variants(
                ranked=ranked,
                query_padded_gray=query_padded_gray,
                cancel_generation=cancel_generation,
                weapons=pair_variant_rerank_target,
            )
            self._ensure_not_cancelled(cancel_generation)
        top1_variant_rerank_attempted = False
        top1_variant_rerank_applied = False
        top1_variant_rerank_weapons: tuple[str, ...] | None = None
        top1_variant_rerank_max_top_score: float | None = None
        top1_variant_rerank_target = self._resolve_top1_variant_rerank_target(
            ranked
        )
        if top1_variant_rerank_target is not None:
            top1_variant_rerank_attempted = True
            top1_variant_rerank_weapons = top1_variant_rerank_target
            top1_variant_rerank_max_top_score = (
                self._resolve_top1_variant_rerank_max_top_score(
                    top1_variant_rerank_target
                )
            )
            (
                ranked,
                top1_variant_rerank_applied,
            ) = await self._rerank_specific_weapons_with_variants(
                ranked=ranked,
                query_padded_gray=query_padded_gray,
                cancel_generation=cancel_generation,
                weapons=top1_variant_rerank_target,
            )
            self._ensure_not_cancelled(cancel_generation)
        (
            accepted_candidate,
            selected_confidence,
            second_confidence,
            rescue_applied,
        ) = self._select_accepted_candidate(
            ranked=ranked,
            slot_signal_metrics=slot_signal_metrics,
        )
        pair_variant_rescue_applied = False
        pair_variant_rescue_gain: float | None = None
        (
            accepted_candidate,
            selected_confidence,
            second_confidence,
            pair_variant_rescue_applied,
            pair_variant_rescue_gain,
        ) = self._maybe_apply_pair_variant_rescue(
            original_ranked=ranked_before_pair_variant_rerank,
            reranked=ranked,
            accepted_candidate=accepted_candidate,
            selected_confidence=selected_confidence,
            second_confidence=second_confidence,
            pair_variant_rerank_target=pair_variant_rerank_target,
        )
        if low_signal_forced_unknown:
            accepted_candidate = None
            rescue_applied = False
            pair_variant_rescue_applied = False
            pair_variant_rescue_gain = None
        variant_fallback_attempted = False
        variant_applied = False
        if (
            not low_signal_forced_unknown
            and not labeling_variant_rerank_applied
            and not pair_variant_rescue_applied
            and self._should_try_variant_fallback(
                accepted_candidate=accepted_candidate,
                selected_confidence=selected_confidence,
                second_confidence=second_confidence,
            )
        ):
            variant_fallback_attempted = True
            ranked_with_variant = (
                await self._rank_weapon_candidates_with_variant(
                    query_padded_gray,
                    cancel_generation=cancel_generation,
                )
            )
            self._ensure_not_cancelled(cancel_generation)
            (
                variant_accepted_candidate,
                variant_selected_confidence,
                variant_second_confidence,
                variant_rescue_applied,
            ) = self._select_accepted_candidate(
                ranked=ranked_with_variant,
                slot_signal_metrics=slot_signal_metrics,
            )
            if self._should_replace_with_variant_result(
                accepted_candidate=accepted_candidate,
                selected_confidence=selected_confidence,
                variant_accepted_candidate=variant_accepted_candidate,
                variant_selected_confidence=variant_selected_confidence,
            ):
                ranked = ranked_with_variant
                accepted_candidate = variant_accepted_candidate
                selected_confidence = variant_selected_confidence
                second_confidence = variant_second_confidence
                rescue_applied = variant_rescue_applied
                variant_applied = True

        top_candidates = tuple(
            WeaponCandidateScore(
                weapon=item.weapon,
                score=item.score,
                threshold=item.template_threshold,
            )
            for item in ranked[:3]
        )
        if accepted_candidate is not None:
            predicted_weapon = accepted_candidate.weapon
            is_unmatched = False
            threshold = accepted_candidate.template_threshold
        else:
            predicted_weapon = constants.UNKNOWN_WEAPON_LABEL
            is_unmatched = True
            threshold = ranked[0].template_threshold if ranked else None

        threshold_matched = [
            item for item in ranked if item.score >= item.template_threshold
        ]
        debug_candidates = tuple(
            unmatched_report.SlotDebugCandidate(
                weapon=item.weapon,
                score=item.score,
                threshold=item.template_threshold,
            )
            for item in ranked[:3]
        )
        self._logger.info(
            "ブキ判別候補",
            slot=slot,
            predicted_weapon=predicted_weapon,
            is_unmatched=is_unmatched,
            threshold=threshold,
            selected_confidence=(
                round(selected_confidence, 6)
                if selected_confidence is not None
                else None
            ),
            selected_confidence_gap=(
                round(selected_confidence - second_confidence, 6)
                if selected_confidence is not None
                and second_confidence is not None
                else None
            ),
            confidence_accept_threshold=round(
                constants.CANDIDATE_CONFIDENCE_ACCEPT_THRESHOLD, 6
            ),
            confidence_rescue_threshold=round(
                constants.CANDIDATE_CONFIDENCE_ACCEPT_THRESHOLD
                - constants.CANDIDATE_CONFIDENCE_RESCUE_MARGIN,
                6,
            ),
            labeling_variant_rerank_attempted=(
                labeling_variant_rerank_attempted
            ),
            labeling_variant_rerank_applied=labeling_variant_rerank_applied,
            labeling_variant_rerank_top_weapons=(
                constants.LABELING_VARIANT_RERANK_TOP_WEAPONS
            ),
            pair_variant_rerank_attempted=pair_variant_rerank_attempted,
            pair_variant_rerank_applied=pair_variant_rerank_applied,
            pair_variant_rerank_weapons=(
                list(pair_variant_rerank_weapons)
                if pair_variant_rerank_weapons is not None
                else None
            ),
            pair_variant_rerank_max_score_gap=(
                round(pair_variant_rerank_max_score_gap, 6)
                if pair_variant_rerank_max_score_gap is not None
                else None
            ),
            top1_variant_rerank_attempted=top1_variant_rerank_attempted,
            top1_variant_rerank_applied=top1_variant_rerank_applied,
            top1_variant_rerank_weapons=(
                list(top1_variant_rerank_weapons)
                if top1_variant_rerank_weapons is not None
                else None
            ),
            top1_variant_rerank_max_top_score=(
                round(top1_variant_rerank_max_top_score, 6)
                if top1_variant_rerank_max_top_score is not None
                else None
            ),
            pair_variant_rescue_applied=pair_variant_rescue_applied,
            pair_variant_rescue_gain=(
                round(pair_variant_rescue_gain, 6)
                if pair_variant_rescue_gain is not None
                else None
            ),
            variant_fallback_attempted=variant_fallback_attempted,
            variant_applied=variant_applied,
            variant_fallback_max_confidence_gap=round(
                constants.VARIANT_FALLBACK_MAX_CONFIDENCE_GAP, 6
            ),
            low_signal_forced_unknown=low_signal_forced_unknown,
            low_signal_edge_ratio_max=round(
                constants.LOW_SIGNAL_EDGE_RATIO_MAX, 6
            ),
            low_signal_team_edge_ratio_max=round(
                constants.LOW_SIGNAL_TEAM_EDGE_RATIO_MAX, 6
            ),
            rescue_applied=rescue_applied,
            slot_edge_ratio=(
                round(slot_signal_metrics.edge_ratio, 6)
                if slot_signal_metrics is not None
                else None
            ),
            slot_team_edge_ratio=(
                round(slot_signal_metrics.team_edge_ratio, 6)
                if slot_signal_metrics is not None
                else None
            ),
            candidates=self._serialize_candidates_for_log(ranked[:3]),
            confidence_candidates=[
                {
                    "weapon": item.weapon,
                    "confidence": round(self._candidate_confidence(item), 6),
                }
                for item in ranked[:3]
            ],
            threshold_matched_candidates=self._serialize_candidates_for_log(
                threshold_matched[:3]
            ),
        )

        return (
            WeaponSlotResult(
                slot=slot,
                predicted_weapon=predicted_weapon,
                is_unmatched=is_unmatched,
                top_candidates=top_candidates,
                detected_score=(
                    accepted_candidate.score
                    if accepted_candidate is not None
                    else None
                ),
            ),
            debug_candidates,
        )

    def _should_apply_confidence_rescue(
        self,
        *,
        best_candidate: _RankedCandidate,
        best_confidence: float,
        second_confidence: float | None,
        slot_signal_metrics: _SlotSignalMetrics | None,
    ) -> bool:
        if slot_signal_metrics is None:
            return False
        if (
            best_candidate.template_threshold
            > constants.CANDIDATE_CONFIDENCE_RESCUE_MAX_THRESHOLD
        ):
            return False
        rescue_threshold = (
            constants.CANDIDATE_CONFIDENCE_ACCEPT_THRESHOLD
            - constants.CANDIDATE_CONFIDENCE_RESCUE_MARGIN
        )
        if best_confidence < rescue_threshold:
            return False
        if (
            second_confidence is not None
            and (best_confidence - second_confidence)
            < constants.CANDIDATE_CONFIDENCE_RESCUE_MIN_GAP
        ):
            return False
        if (
            slot_signal_metrics.edge_ratio
            < constants.CANDIDATE_CONFIDENCE_RESCUE_MIN_EDGE_RATIO
        ):
            return False
        if (
            slot_signal_metrics.team_edge_ratio
            < constants.CANDIDATE_CONFIDENCE_RESCUE_MIN_TEAM_EDGE_RATIO
        ):
            return False
        return True

    def _is_low_signal_slot(
        self,
        *,
        slot_signal_metrics: _SlotSignalMetrics | None,
    ) -> bool:
        if slot_signal_metrics is None:
            return False
        return (
            slot_signal_metrics.edge_ratio
            <= constants.LOW_SIGNAL_EDGE_RATIO_MAX
            and slot_signal_metrics.team_edge_ratio
            <= constants.LOW_SIGNAL_TEAM_EDGE_RATIO_MAX
        )

    def _select_accepted_candidate(
        self,
        *,
        ranked: list[_RankedCandidate],
        slot_signal_metrics: _SlotSignalMetrics | None,
    ) -> tuple[
        _RankedCandidate | None,
        float | None,
        float | None,
        bool,
    ]:
        best_candidate, selected_confidence, second_confidence = (
            self._select_best_candidates_by_confidence(ranked)
        )
        if best_candidate is None or selected_confidence is None:
            return None, None, None, False
        if (
            selected_confidence
            >= constants.CANDIDATE_CONFIDENCE_ACCEPT_THRESHOLD
        ):
            return (
                best_candidate,
                selected_confidence,
                second_confidence,
                False,
            )
        if self._should_apply_confidence_rescue(
            best_candidate=best_candidate,
            best_confidence=selected_confidence,
            second_confidence=second_confidence,
            slot_signal_metrics=slot_signal_metrics,
        ):
            return best_candidate, selected_confidence, second_confidence, True
        return None, selected_confidence, second_confidence, False

    def _should_try_variant_fallback(
        self,
        *,
        accepted_candidate: _RankedCandidate | None,
        selected_confidence: float | None,
        second_confidence: float | None,
    ) -> bool:
        if not self._variant_template_sources_by_weapon:
            return False
        if accepted_candidate is None:
            return True
        if selected_confidence is None or second_confidence is None:
            return False
        confidence_gap = selected_confidence - second_confidence
        return confidence_gap <= constants.VARIANT_FALLBACK_MAX_CONFIDENCE_GAP

    def _resolve_pair_variant_rerank_target(
        self, ranked: list[_RankedCandidate]
    ) -> tuple[str, str] | None:
        if len(ranked) < 2 or not self._variant_template_sources_by_weapon:
            return None
        score_gap = ranked[0].score - ranked[1].score
        top_pair = {ranked[0].weapon, ranked[1].weapon}
        for weapon_pair, max_score_gap in constants.PAIR_VARIANT_RERANK_RULES:
            if top_pair != set(weapon_pair):
                continue
            if score_gap > max_score_gap:
                return None
            if not any(
                weapon in self._variant_template_sources_by_weapon
                for weapon in weapon_pair
            ):
                return None
            return weapon_pair
        return None

    def _resolve_pair_variant_rerank_max_score_gap(
        self, weapons: tuple[str, str]
    ) -> float | None:
        for weapon_pair, max_score_gap in constants.PAIR_VARIANT_RERANK_RULES:
            if set(weapons) == set(weapon_pair):
                return max_score_gap
        return None

    def _resolve_top1_variant_rerank_target(
        self, ranked: list[_RankedCandidate]
    ) -> tuple[str, ...] | None:
        if not ranked or not self._variant_template_sources_by_weapon:
            return None
        top_candidate = ranked[0]
        for (
            dominant_weapon,
            weapons,
            max_top_score,
        ) in constants.TOP1_VARIANT_RERANK_RULES:
            if top_candidate.weapon != dominant_weapon:
                continue
            if top_candidate.score > max_top_score:
                continue
            if not any(
                weapon in self._variant_template_sources_by_weapon
                for weapon in weapons
                if weapon != dominant_weapon
            ):
                continue
            return weapons
        return None

    def _resolve_top1_variant_rerank_max_top_score(
        self, weapons: tuple[str, ...]
    ) -> float | None:
        for (
            dominant_weapon,
            rule_weapons,
            max_top_score,
        ) in constants.TOP1_VARIANT_RERANK_RULES:
            _ = dominant_weapon
            if tuple(rule_weapons) == tuple(weapons):
                return max_top_score
        return None

    def _resolve_pair_variant_rescue_rule(
        self, weapons: tuple[str, str]
    ) -> tuple[str, float] | None:
        for (
            weapon_pair,
            favored_weapon,
            min_gain,
        ) in constants.PAIR_VARIANT_RESCUE_RULES:
            if set(weapons) == set(weapon_pair):
                return favored_weapon, min_gain
        return None

    def _find_ranked_candidate(
        self, ranked: list[_RankedCandidate], weapon: str
    ) -> _RankedCandidate | None:
        for candidate in ranked:
            if candidate.weapon == weapon:
                return candidate
        return None

    def _maybe_apply_pair_variant_rescue(
        self,
        *,
        original_ranked: list[_RankedCandidate],
        reranked: list[_RankedCandidate],
        accepted_candidate: _RankedCandidate | None,
        selected_confidence: float | None,
        second_confidence: float | None,
        pair_variant_rerank_target: tuple[str, str] | None,
    ) -> tuple[
        _RankedCandidate | None,
        float | None,
        float | None,
        bool,
        float | None,
    ]:
        if pair_variant_rerank_target is None:
            return (
                accepted_candidate,
                selected_confidence,
                second_confidence,
                False,
                None,
            )
        rescue_rule = self._resolve_pair_variant_rescue_rule(
            pair_variant_rerank_target
        )
        if rescue_rule is None:
            return (
                accepted_candidate,
                selected_confidence,
                second_confidence,
                False,
                None,
            )

        favored_weapon, min_gain = rescue_rule
        favored_original = self._find_ranked_candidate(
            original_ranked, favored_weapon
        )
        favored_reranked = self._find_ranked_candidate(
            reranked, favored_weapon
        )
        if favored_original is None or favored_reranked is None:
            return (
                accepted_candidate,
                selected_confidence,
                second_confidence,
                False,
                None,
            )

        gain = favored_reranked.score - favored_original.score
        if gain < min_gain - constants.SCORE_TIE_EPSILON:
            return (
                accepted_candidate,
                selected_confidence,
                second_confidence,
                False,
                None,
            )

        opponent_weapon = (
            pair_variant_rerank_target[0]
            if pair_variant_rerank_target[1] == favored_weapon
            else pair_variant_rerank_target[1]
        )
        opponent_reranked = self._find_ranked_candidate(
            reranked, opponent_weapon
        )
        if opponent_reranked is None:
            return (
                accepted_candidate,
                selected_confidence,
                second_confidence,
                False,
                None,
            )
        if (
            favored_reranked.score
            < opponent_reranked.score - constants.SCORE_TIE_EPSILON
        ):
            return (
                accepted_candidate,
                selected_confidence,
                second_confidence,
                False,
                None,
            )

        favored_confidence = self._candidate_confidence(favored_reranked)
        if (
            favored_confidence
            < constants.CANDIDATE_CONFIDENCE_ACCEPT_THRESHOLD
        ):
            return (
                accepted_candidate,
                selected_confidence,
                second_confidence,
                False,
                None,
            )
        if (
            accepted_candidate is not None
            and accepted_candidate.weapon == favored_weapon
        ):
            return (
                accepted_candidate,
                selected_confidence,
                second_confidence,
                False,
                None,
            )
        return (
            favored_reranked,
            favored_confidence,
            self._candidate_confidence(opponent_reranked),
            True,
            gain,
        )

    def _should_replace_with_variant_result(
        self,
        *,
        accepted_candidate: _RankedCandidate | None,
        selected_confidence: float | None,
        variant_accepted_candidate: _RankedCandidate | None,
        variant_selected_confidence: float | None,
    ) -> bool:
        if (
            variant_accepted_candidate is None
            or variant_selected_confidence is None
        ):
            return False
        if accepted_candidate is None or selected_confidence is None:
            return True
        return (
            variant_selected_confidence
            > selected_confidence + constants.SCORE_TIE_EPSILON
        )

    def _select_best_candidates_by_confidence(
        self, ranked: list[_RankedCandidate]
    ) -> tuple[_RankedCandidate | None, float | None, float | None]:
        if not ranked:
            return None, None, None
        sorted_by_confidence = sorted(
            ranked, key=cmp_to_key(self._compare_candidates_by_confidence)
        )
        best = sorted_by_confidence[0]
        best_confidence = self._candidate_confidence(best)
        second_confidence = None
        if len(sorted_by_confidence) >= 2:
            second_confidence = self._candidate_confidence(
                sorted_by_confidence[1]
            )
        return best, best_confidence, second_confidence

    def _compare_candidates_by_confidence(
        self, left: _RankedCandidate, right: _RankedCandidate
    ) -> int:
        left_confidence = self._candidate_confidence(left)
        right_confidence = self._candidate_confidence(right)
        diff = left_confidence - right_confidence
        if diff > constants.SCORE_TIE_EPSILON:
            return -1
        if diff < -constants.SCORE_TIE_EPSILON:
            return 1
        score_diff = left.score - right.score
        if score_diff > constants.SCORE_TIE_EPSILON:
            return -1
        if score_diff < -constants.SCORE_TIE_EPSILON:
            return 1
        if left.weapon < right.weapon:
            return -1
        if left.weapon > right.weapon:
            return 1
        return 0

    def _select_candidate_by_confidence(
        self, ranked: list[_RankedCandidate]
    ) -> tuple[_RankedCandidate | None, float | None]:
        best, best_confidence, _ = self._select_best_candidates_by_confidence(
            ranked
        )
        if best is None or best_confidence is None:
            return None, None
        if best_confidence < constants.CANDIDATE_CONFIDENCE_ACCEPT_THRESHOLD:
            return None, best_confidence
        return best, best_confidence

    def _candidate_confidence(self, candidate: _RankedCandidate) -> float:
        return candidate.score - (
            constants.CANDIDATE_CONFIDENCE_THRESHOLD_WEIGHT
            * candidate.template_threshold
        )

    async def _rank_weapon_candidates(
        self,
        query_padded_gray: np.ndarray,
        *,
        cancel_generation: int,
    ) -> list[_RankedCandidate]:
        return await self._rank_weapon_candidates_from_sources(
            query_padded_gray=query_padded_gray,
            cancel_generation=cancel_generation,
            template_sources_by_weapon=self._template_sources_by_weapon,
        )

    async def _rank_weapon_candidates_with_variant(
        self,
        query_padded_gray: np.ndarray,
        *,
        cancel_generation: int,
    ) -> list[_RankedCandidate]:
        return await self._rank_weapon_candidates_from_sources(
            query_padded_gray=query_padded_gray,
            cancel_generation=cancel_generation,
            template_sources_by_weapon=self._template_sources_with_variant_by_weapon,
        )

    async def _rerank_top_candidates_with_labeling_variants(
        self,
        *,
        ranked: list[_RankedCandidate],
        query_padded_gray: np.ndarray,
        cancel_generation: int,
    ) -> tuple[list[_RankedCandidate], bool]:
        if not ranked or not self._labeling_variant_sources_by_weapon:
            return ranked, False

        target_weapons = {
            candidate.weapon
            for candidate in ranked[
                : constants.LABELING_VARIANT_RERANK_TOP_WEAPONS
            ]
            if candidate.weapon in self._labeling_variant_sources_by_weapon
        }
        if not target_weapons:
            return ranked, False

        target_sources_by_weapon: dict[str, tuple[_TemplateSource, ...]] = {}
        for weapon in target_weapons:
            base_sources = self._template_sources_by_weapon.get(weapon, ())
            labeling_variant_sources = (
                self._labeling_variant_sources_by_weapon.get(weapon, ())
            )
            merged_sources = base_sources + labeling_variant_sources
            if merged_sources:
                target_sources_by_weapon[weapon] = merged_sources
        if not target_sources_by_weapon:
            return ranked, False

        reranked_subset = await self._rank_weapon_candidates_from_sources(
            query_padded_gray=query_padded_gray,
            cancel_generation=cancel_generation,
            template_sources_by_weapon=target_sources_by_weapon,
        )
        return self._merge_reranked_subset(
            ranked=ranked,
            reranked_subset=reranked_subset,
        )

    async def _rerank_specific_weapons_with_variants(
        self,
        *,
        ranked: list[_RankedCandidate],
        query_padded_gray: np.ndarray,
        cancel_generation: int,
        weapons: tuple[str, ...],
    ) -> tuple[list[_RankedCandidate], bool]:
        target_sources_by_weapon: dict[str, tuple[_TemplateSource, ...]] = {}
        for weapon in weapons:
            merged_sources = self._template_sources_with_variant_by_weapon.get(
                weapon, ()
            )
            if merged_sources:
                target_sources_by_weapon[weapon] = merged_sources
        if len(target_sources_by_weapon) < 2:
            return ranked, False

        reranked_subset = await self._rank_weapon_candidates_from_sources(
            query_padded_gray=query_padded_gray,
            cancel_generation=cancel_generation,
            template_sources_by_weapon=target_sources_by_weapon,
        )
        return self._merge_reranked_subset(
            ranked=ranked,
            reranked_subset=reranked_subset,
        )

    def _merge_reranked_subset(
        self,
        *,
        ranked: list[_RankedCandidate],
        reranked_subset: list[_RankedCandidate],
    ) -> tuple[list[_RankedCandidate], bool]:
        reranked_by_weapon = {
            candidate.weapon: candidate for candidate in reranked_subset
        }
        updated_candidates: list[_RankedCandidate] = []
        applied = False
        for candidate in ranked:
            replacement = reranked_by_weapon.get(candidate.weapon)
            if replacement is None:
                updated_candidates.append(candidate)
                continue
            updated_candidates.append(replacement)
            if (
                replacement.score
                > candidate.score + constants.SCORE_TIE_EPSILON
            ):
                applied = True

        def _compare(left: _RankedCandidate, right: _RankedCandidate) -> int:
            diff = left.score - right.score
            if diff > constants.SCORE_TIE_EPSILON:
                return -1
            if diff < -constants.SCORE_TIE_EPSILON:
                return 1
            if left.weapon < right.weapon:
                return -1
            if left.weapon > right.weapon:
                return 1
            return 0

        return sorted(updated_candidates, key=cmp_to_key(_compare)), applied

    async def _rank_weapon_candidates_from_sources(
        self,
        *,
        query_padded_gray: np.ndarray,
        cancel_generation: int,
        template_sources_by_weapon: dict[str, tuple[_TemplateSource, ...]],
    ) -> list[_RankedCandidate]:
        query_padded_bgr = cv2.cvtColor(query_padded_gray, cv2.COLOR_GRAY2BGR)
        candidates: list[_RankedCandidate] = []

        def cancel_check() -> bool:
            return self._is_cancelled(cancel_generation)

        for (
            weapon,
            template_sources,
        ) in template_sources_by_weapon.items():
            self._ensure_not_cancelled(cancel_generation)
            score_tasks = [
                asyncio.create_task(
                    source.matcher.score(
                        query_padded_bgr,
                        cancel_check=cancel_check,
                    )
                )
                for source in template_sources
            ]
            try:
                scores = await asyncio.gather(*score_tasks)
            except BaseException:
                for task in score_tasks:
                    task.cancel()
                await asyncio.gather(*score_tasks, return_exceptions=True)
                raise
            self._ensure_not_cancelled(cancel_generation)
            best_score = -1.0
            best_source: _TemplateSource | None = None
            for source, score in zip(template_sources, scores):
                if score > best_score + constants.SCORE_TIE_EPSILON:
                    best_score = score
                    best_source = source
            candidates.append(
                _RankedCandidate(
                    weapon=weapon,
                    score=best_score,
                    template_source=best_source,
                    template_threshold=(
                        best_source.threshold
                        if best_source is not None
                        else 1.0
                    ),
                )
            )

        if not candidates:
            raise ValueError("ブキ判別候補が空です。")

        def _compare(left: _RankedCandidate, right: _RankedCandidate) -> int:
            diff = left.score - right.score
            if diff > constants.SCORE_TIE_EPSILON:
                return -1
            if diff < -constants.SCORE_TIE_EPSILON:
                return 1
            if left.weapon < right.weapon:
                return -1
            if left.weapon > right.weapon:
                return 1
            return 0

        return sorted(candidates, key=cmp_to_key(_compare))

    def _serialize_candidates_for_log(
        self, candidates: list[_RankedCandidate]
    ) -> list[dict[str, object]]:
        return [
            {
                "weapon": candidate.weapon,
                "score": round(candidate.score, 6),
                "threshold": round(candidate.template_threshold, 6),
            }
            for candidate in candidates
        ]

    def _load_template_sources(
        self,
    ) -> tuple[
        dict[str, tuple[_TemplateSource, ...]],
        dict[str, tuple[_TemplateSource, ...]],
    ]:
        keys = self._settings.matcher_groups.get(
            constants.WEAPON_TEMPLATE_MATCHER_GROUP
        )
        if not keys:
            self._logger.warning(
                "ブキテンプレートグループが未定義",
                group=constants.WEAPON_TEMPLATE_MATCHER_GROUP,
            )
            return {}, {}

        grouped: dict[str, list[_TemplateSource]] = {}
        variant_grouped: dict[str, list[_TemplateSource]] = {}
        for key in keys:
            cfg = self._settings.matchers.get(key)
            if cfg is None:
                self._logger.warning("マッチャー未定義", matcher_key=key)
                continue
            source = self._build_template_source(cfg)
            if source is None:
                continue
            weapon_name = cfg.name or key
            if self._is_variant_template_source(cfg):
                variant_grouped.setdefault(weapon_name, []).append(source)
                continue
            grouped.setdefault(weapon_name, []).append(source)

        # variantしか存在しないブキは通常候補として扱う。
        for weapon, sources in variant_grouped.items():
            if weapon not in grouped:
                grouped[weapon] = list(sources)

        return (
            {
                weapon: tuple(sources)
                for weapon, sources in grouped.items()
                if sources
            },
            {
                weapon: tuple(sources)
                for weapon, sources in variant_grouped.items()
                if sources
            },
        )

    def _load_labeling_variant_sources(
        self,
    ) -> dict[str, tuple[_TemplateSource, ...]]:
        manifest_path = (
            self._assets_dir
            / constants.LABELING_VARIANT_MANIFEST_RELATIVE_PATH
        )
        try:
            records = labeling_variant_bank.load_labeling_variant_records(
                manifest_path
            )
        except labeling_variant_bank.LabelingVariantManifestError as exc:
            self._logger.warning(
                "ラベリング追加テンプレート manifest の読み込みに失敗",
                manifest_path=str(manifest_path),
                error=str(exc),
            )
            return {}
        if not records:
            return {}

        grouped: dict[str, list[_TemplateSource]] = {}
        for record in records:
            base_sources = self._template_sources_by_weapon.get(record.weapon)
            if not base_sources:
                self._logger.warning(
                    "ラベリング追加テンプレートの対象ブキが未定義",
                    weapon=record.weapon,
                    manifest_path=str(manifest_path),
                )
                continue
            source = self._build_template_source_from_paths(
                template_path=record.template_path,
                mask_path=record.mask_path,
                threshold=base_sources[0].threshold,
            )
            if source is None:
                self._logger.warning(
                    "ラベリング追加テンプレートの読み込みをスキップ",
                    weapon=record.weapon,
                    template_path=record.template_path,
                    mask_path=record.mask_path,
                )
                continue
            grouped.setdefault(record.weapon, []).append(source)

        return {
            weapon: tuple(sources)
            for weapon, sources in grouped.items()
            if sources
        }

    def _is_variant_template_source(self, cfg: MatcherConfig) -> bool:
        if not cfg.template_path:
            return False
        normalized_template_path = cfg.template_path.replace("\\", "/")
        return "_variant" in Path(normalized_template_path).stem.casefold()

    def _merge_template_sources(
        self,
        *,
        base: dict[str, tuple[_TemplateSource, ...]],
        addition: dict[str, tuple[_TemplateSource, ...]],
    ) -> dict[str, tuple[_TemplateSource, ...]]:
        merged: dict[str, list[_TemplateSource]] = {}
        for weapon, sources in base.items():
            merged[weapon] = list(sources)
        for weapon, sources in addition.items():
            merged.setdefault(weapon, []).extend(sources)
        return {
            weapon: tuple(sources)
            for weapon, sources in merged.items()
            if sources
        }

    def _build_template_source(
        self, cfg: MatcherConfig
    ) -> _TemplateSource | None:
        if cfg.type != "template":
            return None
        if not cfg.template_path or not cfg.mask_path:
            return None

        template_path = _resolve_asset_path(
            cfg.template_path, assets_dir=self._assets_dir
        )
        mask_path = _resolve_asset_path(
            cfg.mask_path, assets_dir=self._assets_dir
        )
        matcher = TemplateMatcher(
            template_path=template_path,
            mask_path=mask_path,
            threshold=cfg.threshold,
            response_top_k=constants.TEMPLATE_RESPONSE_TOP_K,
        )
        return _TemplateSource(
            matcher=matcher,
            template_path=template_path,
            mask_path=mask_path,
            threshold=cfg.threshold,
        )

    def _build_template_source_from_paths(
        self,
        *,
        template_path: str,
        mask_path: str,
        threshold: float,
    ) -> _TemplateSource | None:
        resolved_template_path = _resolve_asset_path(
            template_path,
            assets_dir=self._assets_dir,
        )
        resolved_mask_path = _resolve_asset_path(
            mask_path,
            assets_dir=self._assets_dir,
        )
        if (
            not resolved_template_path.is_file()
            or not resolved_mask_path.is_file()
        ):
            return None
        matcher = TemplateMatcher(
            template_path=resolved_template_path,
            mask_path=resolved_mask_path,
            threshold=threshold,
            response_top_k=constants.TEMPLATE_RESPONSE_TOP_K,
        )
        return _TemplateSource(
            matcher=matcher,
            template_path=resolved_template_path,
            mask_path=resolved_mask_path,
            threshold=threshold,
        )

    def _resolve_matching_assets_dir(self) -> Path:
        all_template_sources = list(
            self._template_sources_by_weapon.values()
        ) + list(self._variant_template_sources_by_weapon.values())
        for template_sources in all_template_sources:
            if template_sources:
                template_parent = template_sources[0].template_path.parent
                if template_parent.name == "matching":
                    return template_parent
                for ancestor in template_parent.parents:
                    if ancestor.name == "matching":
                        return ancestor
                return template_parent
        matching_dir = self._assets_dir / "matching"
        if matching_dir.exists():
            return matching_dir
        return self._assets_dir


def _resolve_asset_path(path_str: str, *, assets_dir: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    normalized = path_str.replace("\\", "/")
    if normalized.startswith("assets/"):
        normalized = normalized[len("assets/") :]
    return assets_dir / normalized
