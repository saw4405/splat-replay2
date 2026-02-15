"""ブキ表示検出・判別アダプタ。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import cmp_to_key
from pathlib import Path

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

from . import constants, outline_models, unmatched_report
from .query_builder import (
    QuerySlotData,
    build_query_slot_data,
    crop_slot_images,
)
from .team_color import detect_weapon_display_screen


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
        self._template_sources_by_weapon = self._load_template_sources()
        self._matching_assets_dir = self._resolve_matching_assets_dir()

    async def detect_weapon_display(self, frame: Frame) -> bool:
        slot_images = crop_slot_images(frame)
        is_visible, metrics = detect_weapon_display_screen(slot_images)
        self._logger.debug(
            "ブキ表示判定",
            is_visible=is_visible,
            allies_max_distance=metrics.allies_max_distance,
            enemies_max_distance=metrics.enemies_max_distance,
            teams_min_distance=metrics.teams_min_distance,
        )
        return is_visible

    async def recognize_weapons(
        self,
        frame: Frame,
        save_unmatched_report: bool = True,
    ) -> WeaponRecognitionResult:
        if not self._template_sources_by_weapon:
            raise FileNotFoundError(
                "ブキテンプレートが設定されていません。"
                f" matcher_group={constants.WEAPON_TEMPLATE_MATCHER_GROUP}"
            )

        slot_images = crop_slot_images(frame)
        is_visible, metrics = detect_weapon_display_screen(slot_images)
        if not is_visible:
            raise ValueError(
                "ブキ表示画面ではありません。"
                f" allies_max_distance={metrics.allies_max_distance:.2f},"
                f" enemies_max_distance={metrics.enemies_max_distance:.2f},"
                f" teams_min_distance={metrics.teams_min_distance:.2f}"
            )

        model_masks = outline_models.ensure_outline_models(
            assets_dir=self._matching_assets_dir,
            logger=self._logger,
        )
        query_data_by_slot = build_query_slot_data(
            slot_images=slot_images,
            model_masks=model_masks,
        )

        slot_results: dict[str, WeaponSlotResult] = {}
        candidate_thresholds_by_slot: dict[str, dict[str, float]] = {}
        for slot in constants.SLOT_ORDER:
            slot_result, candidate_thresholds = await self._predict_slot(
                slot=slot,
                query=query_data_by_slot[slot],
            )
            slot_results[slot] = slot_result
            candidate_thresholds_by_slot[slot] = candidate_thresholds

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
        if save_unmatched_report and any(
            result.is_unmatched for result in slot_results.values()
        ):
            unmatched_output_dir = unmatched_report.save_unmatched_slots(
                frame=frame,
                query_data_by_slot=query_data_by_slot,
                slot_results=slot_results,
                candidate_thresholds_by_slot=candidate_thresholds_by_slot,
            )
            self._logger.info(
                "未一致スロット出力を保存",
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
        self, *, slot: str, query: QuerySlotData
    ) -> tuple[WeaponSlotResult, dict[str, float]]:
        ranked = await self._rank_weapon_candidates(query.padded_gray)
        accepted_candidate = next(
            (item for item in ranked if item.score >= item.template_threshold),
            None,
        )
        top_candidates = tuple(
            WeaponCandidateScore(weapon=item.weapon, score=item.score)
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
        top_candidate_thresholds = {
            item.weapon: item.template_threshold for item in ranked[:3]
        }
        self._logger.info(
            "ブキ判別候補",
            slot=slot,
            predicted_weapon=predicted_weapon,
            is_unmatched=is_unmatched,
            threshold=threshold,
            candidates=self._serialize_candidates_for_log(ranked[:3]),
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
            ),
            top_candidate_thresholds,
        )

    async def _rank_weapon_candidates(
        self, query_padded_gray: np.ndarray
    ) -> list[_RankedCandidate]:
        query_padded_bgr = cv2.cvtColor(query_padded_gray, cv2.COLOR_GRAY2BGR)
        candidates: list[_RankedCandidate] = []
        for (
            weapon,
            template_sources,
        ) in self._template_sources_by_weapon.items():
            tasks = [
                src.matcher.score(query_padded_bgr) for src in template_sources
            ]
            scores = await asyncio.gather(*tasks)
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

    def _load_template_sources(self) -> dict[str, tuple[_TemplateSource, ...]]:
        keys = self._settings.matcher_groups.get(
            constants.WEAPON_TEMPLATE_MATCHER_GROUP
        )
        if not keys:
            self._logger.warning(
                "ブキテンプレートグループが未定義",
                group=constants.WEAPON_TEMPLATE_MATCHER_GROUP,
            )
            return {}

        grouped: dict[str, list[_TemplateSource]] = {}
        for key in keys:
            cfg = self._settings.matchers.get(key)
            if cfg is None:
                self._logger.warning("マッチャー未定義", matcher_key=key)
                continue
            source = self._build_template_source(cfg)
            if source is None:
                continue
            weapon_name = cfg.name or key
            grouped.setdefault(weapon_name, []).append(source)

        return {
            weapon: tuple(sources)
            for weapon, sources in grouped.items()
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
        )
        return _TemplateSource(
            matcher=matcher,
            template_path=template_path,
            mask_path=mask_path,
            threshold=cfg.threshold,
        )

    def _resolve_matching_assets_dir(self) -> Path:
        for template_sources in self._template_sources_by_weapon.values():
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
