"""結果画面の表彰検出アダプタ。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import cv2
import numpy as np

from splat_replay.application.interfaces import LoggerPort
from splat_replay.domain.models import Frame
from splat_replay.domain.ports import BattleMedalRecognizerPort
from splat_replay.infrastructure.filesystem import ASSETS_DIR
from splat_replay.infrastructure.matchers.utils import imread_unicode


MEDAL_ROI: Final[tuple[int, int, int, int]] = (880, 430, 1370, 710)
MATCH_THRESHOLD: Final[float] = 0.985
MAX_MEDALS: Final[int] = 3
NMS_IOU_THRESHOLD: Final[float] = 0.20


@dataclass(frozen=True)
class _TemplateData:
    color: Literal["gold", "silver"]
    image: np.ndarray
    mask: np.ndarray
    width: int
    height: int


@dataclass(frozen=True)
class _Candidate:
    color: Literal["gold", "silver"]
    x: int
    y: int
    width: int
    height: int
    score: float


class BattleMedalRecognizerAdapter(BattleMedalRecognizerPort):
    """テンプレートマッチングで結果画面の表彰数を抽出する。"""

    def __init__(
        self,
        logger: LoggerPort,
        assets_dir: Path = ASSETS_DIR,
    ) -> None:
        self._logger = logger
        self._assets_dir = assets_dir
        self._templates = (
            self._load_template(
                "gold", "medal_gold.png", "medal_gold_mask.png"
            ),
            self._load_template(
                "silver", "medal_silver.png", "medal_silver_mask.png"
            ),
        )

    async def count_medals(self, frame: Frame) -> tuple[int, int]:
        try:
            return await asyncio.to_thread(self._count_medals_sync, frame)
        except Exception as exc:
            self._logger.warning("表彰検出に失敗しました", error=str(exc))
            return 0, 0

    def _count_medals_sync(self, frame: Frame) -> tuple[int, int]:
        x1, y1, x2, y2 = MEDAL_ROI
        roi = frame[y1:y2, x1:x2]
        candidates: list[_Candidate] = []

        for template in self._templates:
            result = cv2.matchTemplate(
                roi,
                template.image,
                cv2.TM_CCORR_NORMED,
                mask=template.mask,
            )
            normalized = np.nan_to_num(
                result.astype(np.float32, copy=False),
                nan=-1.0,
                posinf=-1.0,
                neginf=-1.0,
            )
            ys, xs = np.where(normalized >= MATCH_THRESHOLD)
            for y, x in zip(ys.tolist(), xs.tolist(), strict=False):
                candidates.append(
                    _Candidate(
                        color=template.color,
                        x=int(x),
                        y=int(y),
                        width=template.width,
                        height=template.height,
                        score=float(normalized[y, x]),
                    )
                )

        kept = self._apply_nms(candidates)[:MAX_MEDALS]
        gold = sum(1 for candidate in kept if candidate.color == "gold")
        silver = sum(1 for candidate in kept if candidate.color == "silver")
        self._logger.debug(
            "表彰検出",
            gold=gold,
            silver=silver,
            candidate_count=len(candidates),
            kept_count=len(kept),
        )
        return gold, silver

    def _load_template(
        self,
        color: Literal["gold", "silver"],
        image_name: str,
        mask_name: str,
    ) -> _TemplateData:
        image_path = self._assets_dir / "matching" / image_name
        mask_path = self._assets_dir / "matching" / mask_name
        image = imread_unicode(image_path)
        mask = imread_unicode(mask_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(
                f"テンプレート画像の読み込みに失敗しました: {image_path}"
            )
        if mask is None:
            raise FileNotFoundError(
                f"テンプレートマスクの読み込みに失敗しました: {mask_path}"
            )
        height, width = image.shape[:2]
        return _TemplateData(
            color=color,
            image=image,
            mask=mask,
            width=width,
            height=height,
        )

    def _apply_nms(self, candidates: list[_Candidate]) -> list[_Candidate]:
        kept: list[_Candidate] = []
        for candidate in sorted(
            candidates, key=lambda item: item.score, reverse=True
        ):
            if all(
                self._iou(candidate, existing) < NMS_IOU_THRESHOLD
                for existing in kept
            ):
                kept.append(candidate)
        return kept

    @staticmethod
    def _iou(left: _Candidate, right: _Candidate) -> float:
        left_x2 = left.x + left.width
        left_y2 = left.y + left.height
        right_x2 = right.x + right.width
        right_y2 = right.y + right.height

        inter_x1 = max(left.x, right.x)
        inter_y1 = max(left.y, right.y)
        inter_x2 = min(left_x2, right_x2)
        inter_y2 = min(left_y2, right_y2)
        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        if inter_w == 0 or inter_h == 0:
            return 0.0

        inter_area = inter_w * inter_h
        left_area = left.width * left.height
        right_area = right.width * right.height
        union_area = left_area + right_area - inter_area
        if union_area <= 0:
            return 0.0
        return inter_area / union_area
