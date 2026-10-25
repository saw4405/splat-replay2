"""保存済みの採用画面上で、既存の認識対象範囲だけを案内する。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Mapping, cast

import cv2
import numpy as np
import yaml

from splat_replay.domain.models import Match, Rule, Stage
from splat_replay.infrastructure.adapters.medal_detection.recognizer import (
    MEDAL_ROI,
)
from splat_replay.infrastructure.adapters.weapon_detection.constants import (
    SLOT_BOXES,
)
from splat_replay.infrastructure.filesystem.paths import (
    ASSETS_DIR,
    IMAGE_MATCHING_FILE,
)
from splat_replay.infrastructure.matchers.utils import imread_unicode

Regions = dict[str, dict[str, tuple[int, int, int, int]]]
Sizes = dict[str, tuple[int, int]]


@lru_cache(maxsize=1)
def _configuration() -> dict[str, object]:
    data = yaml.safe_load(IMAGE_MATCHING_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("画像認識設定が不正です")
    return data


def _template_region(
    image: np.ndarray, group: str, value: str
) -> tuple[int, int, int, int] | None:
    config = _configuration()
    groups, specs = config.get("matcher_groups"), config.get("simple_matchers")
    if not isinstance(groups, dict) or not isinstance(specs, dict):
        return None
    for key in groups.get(group, []):
        spec = specs.get(key)
        if (
            not isinstance(spec, dict)
            or spec.get("type") != "template"
            or spec.get("name") != value
        ):
            continue
        template = imread_unicode(
            ASSETS_DIR / str(spec["template_path"]).removeprefix("assets/")
        )
        if template is None:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        roi = spec.get("roi", {})
        x = int(roi.get("x", 0))
        y = int(roi.get("y", 0))
        gray = gray[
            y : y + int(roi.get("height", gray.shape[0])),
            x : x + int(roi.get("width", gray.shape[1])),
        ]
        mask = (
            imread_unicode(
                ASSETS_DIR / str(spec["mask_path"]).removeprefix("assets/"),
                cv2.IMREAD_GRAYSCALE,
            )
            if spec.get("mask_path")
            else None
        )
        # TemplateMatcherと同じ画像・mask・相関係数・閾値で、値を変えず位置だけ再測定する。
        response = cv2.matchTemplate(
            gray,
            cv2.cvtColor(template, cv2.COLOR_BGR2GRAY),
            cv2.TM_CCOEFF_NORMED,
            mask=mask,
        )
        finite = np.where(np.isfinite(response), response, -1.0)
        _, score, _, location = cv2.minMaxLoc(finite)
        if score >= float(spec.get("threshold", 0.9)):
            return (
                x + location[0],
                y + location[1],
                template.shape[1],
                template.shape[0],
            )
    return None


def build_evidence_annotations(
    paths: Mapping[str, Path], metadata: Mapping[str, object]
) -> tuple[Regions, Sizes]:
    regions: Regions = {}
    sizes: Sizes = {}
    for kind, path in paths.items():
        image = imread_unicode(path)
        if image is None:
            continue
        sizes[kind] = (image.shape[1], image.shape[0])
        fields: dict[str, tuple[int, int, int, int]] = {}
        if kind == "weapons":
            for slot, (x1, y1, x2, y2) in SLOT_BOXES.items():
                team, index = slot.split("_")
                fields[
                    f"{'allies' if team == 'ally' else 'enemies'}_{int(index) - 1}"
                ] = (x1 - 500, y1 - 10, x2 - x1, y2 - y1)
        elif kind == "judgement":
            fields["judgement"] = (0, 0, image.shape[1], image.shape[0])
        elif kind == "result_full":
            for field, enum, group in (
                ("rule", Rule, "battle_rules"),
                ("stage", Stage, "battle_stages"),
            ):
                raw = metadata.get(field)
                if isinstance(raw, str) and raw in enum.__members__:
                    box = _template_region(image, group, enum[raw].value)
                    if box is not None:
                        fields[field] = box
            # OCRが保持しない採用候補番号を推測せず、既存全候補を含む範囲を示す。
            fields.update(
                kill=(1519, 293, 66, 139),
                death=(1597, 293, 47, 139),
                special=(1674, 293, 29, 139),
            )
            x1, y1, x2, y2 = MEDAL_ROI
            fields["gold_medals"] = fields["silver_medals"] = (
                x1,
                y1,
                x2 - x1,
                y2 - y1,
            )
        elif kind == "match_select":
            raw = metadata.get("match")
            match = (
                Match.__members__.get(raw) if isinstance(raw, str) else None
            )
            fields["match"] = (
                (520, 480, 290, 120)
                if match is not None and match.is_fest()
                else (280, 390, 20, 20)
            )
            if metadata.get("rate") is not None:
                if match is Match.X:
                    fields["rate"] = (1730, 190, 150, 50)
                elif match is Match.CHALLENGE:
                    fields["rate"] = (1710, 190, 150, 50)
                elif match is not None and match.is_anarchy():
                    box = _template_region(
                        image, "battle_rate_udemae", str(metadata["rate"])
                    )
                    if box is not None:
                        fields["rate"] = box
        regions[kind] = fields
    return regions, sizes


def parse_evidence_annotations(
    data: Mapping[str, object],
) -> tuple[Regions, Sizes]:
    regions: Regions = {}
    sizes: Sizes = {}
    raw_regions, raw_sizes = (
        data.get("evidence_regions", {}),
        data.get("evidence_sizes", {}),
    )
    if isinstance(raw_regions, dict):
        for kind, fields in raw_regions.items():
            if not isinstance(kind, str) or not isinstance(fields, dict):
                continue
            regions[kind] = {}
            for key, box in fields.items():
                if (
                    isinstance(key, str)
                    and isinstance(box, (list, tuple))
                    and len(box) == 4
                    and all(isinstance(value, int) for value in box)
                ):
                    regions[kind][key] = cast(
                        tuple[int, int, int, int], tuple(box)
                    )
    if isinstance(raw_sizes, dict):
        for kind, size in raw_sizes.items():
            if (
                isinstance(kind, str)
                and isinstance(size, (list, tuple))
                and len(size) == 2
                and all(isinstance(value, int) for value in size)
            ):
                sizes[kind] = cast(tuple[int, int], tuple(size))
    return regions, sizes
