"""スプラトゥーン対戦モード用フレームアナライザー。"""

from __future__ import annotations

import asyncio
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
from structlog.stdlib import BoundLogger

from splat_replay.domain.models import (
    XP,
    BattleResult,
    Frame,
    Judgement,
    Match,
    RateBase,
    Rule,
    Stage,
    Udemae,
)

from .analyzer_plugin import AnalyzerPlugin
from .image_editor import ImageEditorFactory
from .image_matcher import ImageMatcherPort
from .ocr import OCRPort


class BattleFrameAnalyzer(AnalyzerPlugin):
    """バトル向けフレーム解析ロジック。"""

    def __init__(
        self,
        matcher: ImageMatcherPort,
        ocr: OCRPort,
        image_editor_factory: ImageEditorFactory,
        logger: BoundLogger,
    ) -> None:
        self.matcher = matcher
        self._logger = logger
        self.ocr = ocr
        self.image_editor_factory = image_editor_factory
        # 軽量キャッシュ (単一プロセス内での同一フレーム反復呼び出し高速化)
        self._xp_cache: Dict[int, XP] = {}
        self._result_cache: Dict[int, BattleResult] = {}

    # ---------------------------------------------------------------
    # 内部ユーティリティ
    # ---------------------------------------------------------------
    def _fingerprint(self, arr: np.ndarray) -> int:
        """高速な簡易ハッシュ (画素サブサンプリング + 合計)"""
        # サブサンプリングで計算量削減 (BGR 先頭チャネルのみ)
        sample = arr[::64, ::64, 0]
        return int(sample.sum()) & 0xFFFFFFFF

    async def _ensure_ocr_warm(self) -> None:
        # OCR のウォームアップは重いので、ここでは行わない
        return None

    async def extract_match_select(self, frame: Frame) -> Optional[Match]:
        match = await self.matcher.matched_name("battle_select", frame)
        return Match(match) if match else None

    async def extract_rate(
        self, frame: Frame, match: Match
    ) -> Optional[RateBase]:
        """レートを取得する。"""
        if match.is_anarchy():
            udemae = await self.matcher.matched_name(
                "battle_rate_udemae", frame
            )
            return Udemae(udemae) if udemae else None

        if match is Match.X:
            return await self.extract_xp(frame)

        return None

    async def extract_xp(self, frame: Frame) -> Optional[XP]:
        """XPを取得する。"""
        xp_image = frame[190:240, 1730:1880]
        fp = self._fingerprint(xp_image)
        cached = self._xp_cache.get(fp)
        if cached is not None:
            return cached
        # 変換コストの高い処理はキャッシュミス時のみ実行
        xp_proc = (
            self.image_editor_factory(xp_image)
            .rotate(-4)
            .resize(2, 2)
            .binarize()
            .invert()
            .image
        )
        xp_str = await self.ocr.recognize_text(
            xp_proc, ps_mode="SINGLE_LINE", whitelist="0123456789."
        )
        if xp_str is None:
            self._logger.warning("XパワーのOCRに失敗しました")
            return None
        xp_str = xp_str.strip()

        try:
            xp = float(xp_str)
        except ValueError:
            self._logger.warning(f"Xパワーが数値ではありません: {xp_str}")
            return None
        value = XP(xp)
        self._xp_cache[fp] = value
        return value

    async def detect_session_start(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_start", frame)

    async def detect_session_abort(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_abort", frame)

    async def detect_communication_error(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_communication_error", frame)

    async def detect_session_finish(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_finish", frame)

    async def detect_session_finish_end(self, frame: Frame) -> bool:
        return await self.detect_session_judgement(frame)

    async def detect_session_judgement(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_judgement_latter_half", frame)

    async def extract_session_judgement(
        self, frame: Frame
    ) -> Optional[Judgement]:
        """勝敗画面から勝敗を取得する。"""
        judgement = await self.matcher.matched_name("battle_judgements", frame)
        return Judgement(judgement) if judgement else None

    async def detect_session_result(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_result", frame)

    async def extract_session_result(
        self, frame: Frame
    ) -> Optional[BattleResult]:
        """結果画面から試合結果を抽出する (可能な部分を並列化)。"""
        fp = self._fingerprint(frame)
        cached = self._result_cache.get(fp)
        if cached is not None:
            return cached

        match = await self.extract_battle_match(frame)
        if match is None:
            self._logger.warning("バトルマッチが抽出できません")
            return None

        # ルール / ステージ / キルレコード を並列取得
        rule_task = asyncio.create_task(self.extract_battle_rule(frame))
        stage_task = asyncio.create_task(self.extract_battle_stage(frame))
        kill_task = asyncio.create_task(
            self.extract_battle_kill_record(frame, match)
        )

        rule, stage, kill_record = await asyncio.gather(
            rule_task, stage_task, kill_task
        )

        if rule is None:
            self._logger.warning("バトルルールが抽出できません")
            return None
        if stage is None:
            self._logger.warning("バトルステージが抽出できません")
            return None
        if kill_record is None:
            self._logger.warning("キルレコードが抽出できません")
            return None
        result = BattleResult(
            match=match,
            rule=rule,
            stage=stage,
            kill=kill_record[0],
            death=kill_record[1],
            special=kill_record[2],
        )
        self._result_cache[fp] = result
        return result

    async def extract_battle_match(self, frame: Frame) -> Optional[Match]:
        """バトルマッチの種類を取得する。"""
        match_name = await self.matcher.matched_name("battle_matches", frame)
        return Match(match_name) if match_name else None

    async def extract_battle_rule(self, frame: Frame) -> Optional[Rule]:
        """バトルルールを取得する。"""
        rule_name = await self.matcher.matched_name("battle_rules", frame)
        return Rule(rule_name) if rule_name else None

    async def extract_battle_stage(self, frame: Frame) -> Optional[Stage]:
        """バトルステージを取得する。"""
        stage_name = await self.matcher.matched_name("battle_stages", frame)
        return Stage(stage_name) if stage_name else None

    async def extract_battle_kill_record(
        self, frame: Frame, match: Match, rule: Optional[Rule] = None
    ) -> Optional[Tuple[int, int, int]]:
        """キルレコードを取得する。"""
        record_positions: Dict[str, Dict[str, int]] = {
            "kill": {"x1": 1519, "y1": 293, "x2": 1548, "y2": 316},
            "death": {"x1": 1597, "y1": 293, "x2": 1626, "y2": 316},
            "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316},
        }

        kill_record = await self._extract_battle_kill_record(
            frame, record_positions
        )

        # トリカラの攻撃側のときはキルレ表示の位置が異なるため、再度抽出する
        if not kill_record and match == Match.TRICOLOR:
            record_positions = {
                "kill": {"x1": 1556, "y1": 293, "x2": 1585, "y2": 316},
                "death": {"x1": 1616, "y1": 293, "x2": 1644, "y2": 316},
                "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316},
            }
            kill_record = await self._extract_battle_kill_record(
                frame, record_positions
            )

        return kill_record

    async def _extract_battle_kill_record(
        self, frame: Frame, record_positions: Dict[str, Dict[str, int]]
    ) -> Optional[Tuple[int, int, int]]:
        """キル/デス/スペシャルの値を各ROIでOCRして取得（安定版）。"""
        records: Dict[str, int] = {}
        ocr_tasks: List[asyncio.Task[Optional[str]]] = []
        names: List[str] = []
        for name, position in record_positions.items():
            raw = frame[
                position["y1"] : position["y2"],
                position["x1"] : position["x2"],
            ]
            editor = (
                self.image_editor_factory(raw)
                .resize(3, 3)
                .padding(50, 50, 50, 50, (0, 0, 0))
                .binarize()
            )
            # Kill は 2桁の '1' が細く消えやすいので erode を避ける
            if name in ("death", "special"):
                editor = editor.erode((2, 2), 2)
            # Add erosion for kill to reduce spurious thin '1' noise
            if name == "kill":
                editor = editor.erode((2, 2), 2)
            proc0 = editor.invert().image
            # For kill, crop to the right-most digit cluster when a thin left noise exists
            if name == "kill":
                try:
                    arr = np.asarray(proc0)
                    col_active = (arr < 128).sum(axis=0) > 0
                    idx = np.where(col_active)[0]
                    if idx.size > 0:
                        runs: List[Tuple[int, int]] = []
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
                        if len(runs) >= 2:
                            s1, e1 = runs[-2]
                            s2, e2 = runs[-1]
                            w1 = e1 - s1 + 1
                            # 小さすぎる左クラスターはノイズとみなす
                            if w1 <= 6:
                                rs, re_idx = s2, e2
                            else:
                                rs, re_idx = s1, e2
                        else:
                            rs, re_idx = runs[-1]
                        proc = proc0[:, rs : re_idx + 1]
                    else:
                        proc = proc0
                except Exception:
                    proc = proc0
            else:
                proc = proc0
            task = asyncio.create_task(
                self.ocr.recognize_text(
                    proc, ps_mode="SINGLE_LINE", whitelist="0123456789"
                )
            )
            ocr_tasks.append(task)
            names.append(name)

        ocr_results = await asyncio.gather(*ocr_tasks, return_exceptions=True)

        for name, result in zip(names, ocr_results):
            if (
                isinstance(result, Exception)
                or result is None
                or not isinstance(result, str)
            ):
                self._logger.warning(f"{name}数のOCRに失敗しました")
                return None
            text = result.strip()
            # 末尾の連続数字のみ採用し、装飾/記号の混入を除去
            m = re.search(r"(\d+)\D*$", text)
            digits = m.group(1) if m else ""
            if not digits:
                self._logger.warning(f"{name}数が数値ではありません: {text}")
                return None
            # 先頭ゼロ除去（全てゼロなら0）
            if digits.startswith("0"):
                digits = digits.lstrip("0") or "0"
            # death/special は 1桁優先（誤って2桁になった場合は末尾1桁）
            if name in ("death", "special") and len(digits) >= 2:
                digits = digits[-1]
            try:
                records[name] = int(digits)
            except ValueError:
                self._logger.warning(f"{name}数が数値ではありません: {text}")

        if len(records) != 3:
            return None
        return records["kill"], records["death"], records["special"]

    async def _extract_battle_kill_record_fast(
        self, frame: Frame, record_positions: Dict[str, Dict[str, int]]
    ) -> Optional[Tuple[int, int, int]]:
        order = ["kill", "death", "special"]
        rois: List[np.ndarray] = []
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
                self.image_editor_factory(raw)
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

        text = await self.ocr.recognize_text(
            stacked, ps_mode="SINGLE_COLUMN", whitelist="0123456789"
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
