"""キルレコード抽出ロジック。"""

from __future__ import annotations

import asyncio
import re
from typing import Optional

import numpy as np
from splat_replay.domain.models import Frame, Match
from splat_replay.domain.ports import ImageEditorFactory, OCRPort, OCRPurpose


class KillRecordExtractor:
    """キルレコードの抽出を担当するクラス。"""

    def __init__(
        self, ocr: OCRPort, image_editor_factory: ImageEditorFactory
    ) -> None:
        self._ocr = ocr
        self._image_editor_factory = image_editor_factory

    async def extract_battle_kill_record(
        self, frame: Frame, match: Match
    ) -> Optional[tuple[int, int, int]]:
        """キルレコードを取得する。"""
        candidate_positions: list[dict[str, dict[str, int]]] = [
            {
                "kill": {"x1": 1519, "y1": 293, "x2": 1548, "y2": 316},
                "death": {"x1": 1597, "y1": 293, "x2": 1626, "y2": 316},
                "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316},
            },
            {
                "kill": {"x1": 1519, "y1": 410, "x2": 1548, "y2": 432},
                "death": {"x1": 1597, "y1": 410, "x2": 1626, "y2": 432},
                "special": {"x1": 1674, "y1": 410, "x2": 1703, "y2": 432},
            },
        ]

        # トリカラの攻撃側のときはキルレ表示の位置が異なるため、再度抽出する
        if match == Match.TRICOLOR:
            candidate_positions.append(
                {
                    "kill": {"x1": 1556, "y1": 293, "x2": 1585, "y2": 316},
                    "death": {"x1": 1616, "y1": 293, "x2": 1644, "y2": 316},
                    "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316},
                }
            )

        for record_positions in candidate_positions:
            kill_record = await self._extract_battle_kill_record(
                frame, record_positions
            )
            if kill_record is not None:
                return kill_record

        return None

    async def _extract_battle_kill_record(
        self, frame: Frame, record_positions: dict[str, dict[str, int]]
    ) -> Optional[tuple[int, int, int]]:
        """キル/デス/スペシャルの値を各ROIでOCRして取得（安定版）。"""
        records: dict[str, int] = {}
        ocr_tasks: list[asyncio.Task[Optional[str]]] = []
        names: list[str] = []
        fragmented_stat_names: set[str] = set()
        raw_images: dict[str, Frame] = {}
        legacy_primary_images: dict[str, Frame] = {}
        purposes: dict[str, OCRPurpose] = {}
        for name, position in record_positions.items():
            purpose = _ocr_purpose_for_stat(name)
            raw = frame[
                position["y1"] : position["y2"],
                position["x1"] : position["x2"],
            ]
            if int(np.max(raw)) == int(np.min(raw)):
                return None
            raw_images[name] = raw
            purposes[name] = purpose
            editor = (
                self._image_editor_factory(raw)
                .resize(3, 3)
                .padding(50, 50, 50, 50, (0, 0, 0))
                .binarize()
            )
            # death/special も適度に erode してノイズ除去
            if name in ("death", "special"):
                editor = editor.erode((2, 2), 2)
            # Kill は弱めの侵食で細いノイズを減らしつつ数字の形を維持する
            if name == "kill":
                editor = editor.erode((2, 2), 2)
            proc0 = editor.invert().image
            if name in ("death", "special"):
                try:
                    ds_runs = self._active_column_runs(proc0)
                    if ds_runs and not self._looks_like_separate_digit_runs(
                        ds_runs
                    ):
                        rs = ds_runs[0][0]
                        re_idx = ds_runs[-1][1]
                        # 桁の端まで切ると細い「1」が落ちるため、横に余白を残す。
                        proc = proc0[
                            :, max(0, rs - 5) : min(proc0.shape[1], re_idx + 6)
                        ]
                        fragmented_stat_names.add(name)
                    else:
                        proc = proc0
                except Exception:
                    proc = proc0
            else:
                # killはクラスタ分割せず、ROI全体をOCRする。
                proc = proc0

            # bbox 前の従来 primary を fallback に使えるよう保持する。
            legacy_primary_images[name] = proc

            # 前景の外接矩形に切り出し、OCRしやすい白15pxの余白を加える。
            foreground_y, foreground_x = np.where(np.asarray(proc) < 128)
            if foreground_x.size:
                x1 = int(foreground_x.min())
                x2 = int(foreground_x.max()) + 1
                y1 = int(foreground_y.min())
                y2 = int(foreground_y.max()) + 1
                proc = np.pad(
                    proc[y1:y2, x1:x2],
                    ((15, 15), (15, 15)),
                    mode="constant",
                    constant_values=255,
                )

            task = asyncio.create_task(
                self._ocr.recognize_text(
                    proc,
                    ps_mode="SINGLE_LINE",
                    whitelist="0123456789",
                    purpose=purpose,
                )
            )
            ocr_tasks.append(task)
            names.append(name)

        ocr_results = await asyncio.gather(*ocr_tasks, return_exceptions=True)

        for name, result in zip(names, ocr_results):
            primary_text = result if isinstance(result, str) else None
            primary_digits = self._extract_numeric_ocr_digits(primary_text)
            parsed = (
                self._parse_fragmented_stat_ocr_result(primary_text)
                if name in fragmented_stat_names
                else self._parse_numeric_ocr_result(primary_text)
            )
            if parsed is None or len(primary_digits) < 2:
                fallback_text = await self._recognize_fixed_width_stat(
                    raw_images[name],
                    purposes[name],
                    legacy_primary_images[name],
                )
                fallback_digits = self._extract_numeric_ocr_digits(
                    fallback_text
                )
                fallback_parsed = self._parse_numeric_ocr_result(fallback_text)
                if len(fallback_digits) == 2 and fallback_parsed is not None:
                    parsed = fallback_parsed
            if parsed is None:
                return None
            records[name] = parsed

        if len(records) != 3:
            return None
        return records["kill"], records["death"], records["special"]

    @staticmethod
    def _active_column_runs(image: np.ndarray) -> list[tuple[int, int]]:
        arr = np.asarray(image)
        col_active = (arr < 128).sum(axis=0) > 0
        idx = np.where(col_active)[0]
        if idx.size == 0:
            return []

        runs: list[tuple[int, int]] = []
        start = int(idx[0])
        end = int(idx[0])
        for point in map(int, idx[1:]):
            if point == end + 1:
                end = point
            else:
                runs.append((start, end))
                start = point
                end = point
        runs.append((start, end))
        return runs

    @staticmethod
    def _looks_like_separate_digit_runs(runs: list[tuple[int, int]]) -> bool:
        if len(runs) < 2:
            return False

        widths = [end - start + 1 for start, end in runs]
        gaps = [
            runs[index + 1][0] - runs[index][1] - 1
            for index in range(len(runs) - 1)
        ]
        max_width = max(widths)
        max_gap = max(gaps)
        return max_gap > max_width * 0.75 and max_width <= 24

    async def _recognize_fixed_width_stat(
        self,
        raw: Frame,
        purpose: OCRPurpose,
        legacy_primary: Frame,
    ) -> Optional[str]:
        """二桁表示が途中で欠落した場合に、最小前処理で再認識する。"""
        raw_text = await self._ocr.recognize_text(
            raw,
            ps_mode="SINGLE_LINE",
            whitelist="0123456789",
            purpose=purpose,
        )
        if len(self._extract_numeric_ocr_digits(raw_text)) == 2:
            return raw_text

        legacy_primary_text = await self._ocr.recognize_text(
            legacy_primary,
            ps_mode="SINGLE_LINE",
            whitelist="0123456789",
            purpose=purpose,
        )
        if len(self._extract_numeric_ocr_digits(legacy_primary_text)) == 2:
            return legacy_primary_text

        latest_text: Optional[str] = None
        for scale, padding, erosion in (
            (1, 0, 0),
            (1, 0, 1),
            (1, 5, 2),
        ):
            editor = (
                self._image_editor_factory(raw)
                .resize(scale, scale)
                .padding(padding, padding, padding, padding, (0, 0, 0))
                .binarize()
            )
            if erosion:
                editor = editor.erode((2, 2), erosion)
            latest_text = await self._ocr.recognize_text(
                editor.invert().image,
                ps_mode="SINGLE_LINE",
                whitelist="0123456789",
                purpose=purpose,
            )
            if len(self._extract_numeric_ocr_digits(latest_text)) == 2:
                return latest_text
        return latest_text

    @staticmethod
    def _extract_numeric_ocr_digits(text: Optional[str]) -> str:
        if text is None:
            return ""
        match = re.search(r"(\d+)\D*$", text.strip())
        return match.group(1) if match else ""

    @staticmethod
    def _parse_numeric_ocr_result(text: Optional[str]) -> Optional[int]:
        if text is None:
            return None
        stripped = text.strip()
        if not stripped:
            return None
        digits = KillRecordExtractor._extract_numeric_ocr_digits(stripped)
        if not digits:
            return None
        digits = digits.lstrip("0") or "0"
        if len(digits) >= 3:
            value = int(digits)
            if value >= 100:
                digits = digits[1:]
        try:
            return int(digits)
        except ValueError:
            return None

    @staticmethod
    def _parse_fragmented_stat_ocr_result(
        text: Optional[str],
    ) -> Optional[int]:
        if text is None:
            return None
        stripped = text.strip()
        if not stripped:
            return None
        digits = KillRecordExtractor._extract_numeric_ocr_digits(stripped)
        if not digits:
            return None
        if len(digits) >= 2 and digits.startswith("0"):
            digits = digits[-1]
        return KillRecordExtractor._parse_numeric_ocr_result(digits)

    async def _extract_battle_kill_record_fast(
        self, frame: Frame, record_positions: dict[str, dict[str, int]]
    ) -> Optional[tuple[int, int, int]]:
        order = ["kill", "death", "special"]
        rois: list[np.ndarray] = []
        for key in order:
            pos = record_positions[key]
            x1, y1, x2, y2 = pos["x1"], pos["y1"], pos["x2"], pos["y2"]
            mx = 2
            raw = frame[
                y1:y2,
                max(x1 + mx, x1) : max(x1 + mx, x1)
                + max((x2 - x1) - 2 * mx, 1),
            ]
            proc = (
                self._image_editor_factory(raw)
                .resize(3, 3)
                .padding(50, 50, 50, 50, (0, 0, 0))
                .binarize()
                .invert()
                .image
            )
            try:
                import numpy as _np

                arr = _np.asarray(proc)
                col_active = (arr < 128).sum(axis=0) > 0
                idx = _np.where(col_active)[0]
                if idx.size > 0:
                    runs: list[tuple[int, int]] = []
                    s = int(idx[0])
                    e = int(idx[0])
                    for p in map(int, idx[1:]):
                        if p == e + 1:
                            e = p
                        else:
                            runs.append((s, e))
                            s = p
                            e = p
                    runs.append((s, e))
                    if key in ("death", "special"):
                        # death/special は末尾 run のみ
                        rs, end_idx = runs[-1]
                        roi = proc[:, rs : end_idx + 1]
                    else:
                        if len(runs) >= 2:
                            rs = runs[-2][0]
                            end_idx = runs[-1][1]
                        else:
                            rs, end_idx = runs[-1]
                        roi = proc[:, rs : end_idx + 1]
                else:
                    roi = proc
            except Exception:
                roi = proc
            rois.append(roi)

        # Stack vertically with separators and OCR once
        try:
            max_w = max(r.shape[1] for r in rois)

            def _pad(a: np.ndarray, w: int) -> np.ndarray:
                if a.shape[1] >= w:
                    return a
                pad = np.zeros((a.shape[0], w - a.shape[1]), dtype=a.dtype)
                return np.concatenate([a, pad], axis=1)

            rois_p = [_pad(r, max_w) for r in rois]
            sep = np.zeros((20, max_w), dtype=rois_p[0].dtype)
            stacked = np.concatenate(
                [rois_p[0], sep, rois_p[1], sep, rois_p[2]], axis=0
            )
        except Exception:
            stacked = rois[0]

        def _parse_int(s: Optional[str]) -> Optional[int]:
            if s is None:
                return None
            m = re.search(r"(\d+)\D*$", s)
            digits = m.group(1) if m else ""
            if not digits:
                return None
            if digits.startswith("0"):
                if len(digits) >= 2 and digits[1] == "1":
                    digits = digits[-1]
                else:
                    digits = digits.lstrip("0") or "0"
            try:
                return int(digits)
            except ValueError:
                return None

        text = await self._ocr.recognize_text(
            stacked,
            ps_mode="SINGLE_COLUMN",
            whitelist="0123456789",
            purpose=OCRPurpose.BATTLE_KILL_RECORD,
        )
        if text is None:
            return None
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 3:
            return None
        vals: list[int] = []
        for line_idx, ln in enumerate(lines[:3]):
            v = _parse_int(ln)
            # death/special は誤って2桁になるケースがあるため末尾1桁を優先
            if v is None:
                return None
            if line_idx in (1, 2) and v >= 10:
                # 可能なら末尾桁を採用
                m2 = re.search(r"(\d+)\D*$", ln)
                d2 = m2.group(1) if m2 else ""
                if len(d2) >= 2:
                    try:
                        v = int(d2[-1])
                    except Exception:
                        pass
            if v is None:
                return None
            vals.append(v)
        return int(vals[0]), int(vals[1]), int(vals[2])


def _ocr_purpose_for_stat(name: str) -> OCRPurpose:
    """キルレコード項目を OCR の意味的用途へ変換する。"""
    purposes = {
        "kill": OCRPurpose.BATTLE_KILL,
        "death": OCRPurpose.BATTLE_DEATH,
        "special": OCRPurpose.BATTLE_SPECIAL,
    }
    try:
        return purposes[name]
    except KeyError as exc:
        raise ValueError(f"未知のキルレコード項目: {name}") from exc
