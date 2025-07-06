"""動画編集サービス。"""

from __future__ import annotations

from pathlib import Path
import datetime
from collections import defaultdict
from typing import Dict, List, Tuple
import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from splat_replay.infrastructure.adapters.ffmpeg_processor import (
    FFmpegProcessor,
)

from splat_replay.domain.models.play import Play
from splat_replay.domain.models.video_clip import VideoClip
from splat_replay.domain.models import (
    VideoAsset,
    BattleResult,
    SalmonResult,
    RateBase,
)
from splat_replay.shared.config import AppSettings
from splat_replay.shared.logger import get_logger

logger = get_logger()


class VideoEditor:
    """FFmpeg 等を用いた動画編集処理を提供する。"""

    THUMBNAIL_ASSETS_DIR = Path("assets/thumbnail")

    TIME_RANGES: List[Tuple[datetime.time, datetime.time]] = [
        (datetime.time(1, 0), datetime.time(3, 0)),
        (datetime.time(3, 0), datetime.time(5, 0)),
        (datetime.time(5, 0), datetime.time(7, 0)),
        (datetime.time(7, 0), datetime.time(9, 0)),
        (datetime.time(9, 0), datetime.time(11, 0)),
        (datetime.time(11, 0), datetime.time(13, 0)),
        (datetime.time(13, 0), datetime.time(15, 0)),
        (datetime.time(15, 0), datetime.time(17, 0)),
        (datetime.time(17, 0), datetime.time(19, 0)),
        (datetime.time(19, 0), datetime.time(21, 0)),
        (datetime.time(21, 0), datetime.time(23, 0)),
        (datetime.time(23, 0), datetime.time(1, 0)),
    ]

    def __init__(self, ffmpeg: "FFmpegProcessor") -> None:
        self.ffmpeg = ffmpeg

    def process(self, assets: List[VideoAsset]) -> List[Path]:
        """複数の動画をまとめて編集する."""
        groups = self._group_assets(assets)
        outputs: List[Path] = []
        settings = AppSettings.load_from_toml(Path("config/settings.toml"))
        vol = settings.video_edit.volume_multiplier
        for key, group in groups.items():
            if not group:
                continue
            if len(group) > 1:
                merged = self.ffmpeg.merge([a.video for a in group])
                target = VideoAsset.load(merged)
                target.metadata = group[0].metadata
            else:
                target = group[0]
            day, time_slot, match_name, rule_name = key
            title, description = self._generate_title_and_description(
                group,
                day,
                time_slot,
                match_name,
                rule_name,
            )
            logger.info("タイトル生成", title=title)
            logger.debug("説明生成", description=description)
            thumb = self._create_thumbnail(group)
            if thumb:
                logger.info("サムネイル生成", thumbnail=str(thumb))
            try:
                self.ffmpeg.embed_metadata(target.video, title, description)
            except Exception as e:  # pragma: no cover - 埋め込み失敗は警告のみ
                logger.warning("メタデータ埋め込み失敗", error=str(e))
            if thumb:
                try:
                    self.ffmpeg.embed_thumbnail(target.video, thumb)
                except Exception as e:  # pragma: no cover
                    logger.warning("サムネイル埋め込み失敗", error=str(e))
            if target.subtitle:
                try:
                    self.ffmpeg.embed_subtitle(target.video, target.subtitle)
                except Exception as e:  # pragma: no cover - 失敗しても続行
                    logger.warning("字幕埋め込み失敗", error=str(e))
            try:
                self.ffmpeg.change_volume(target.video, vol)
            except Exception as e:  # pragma: no cover
                logger.warning("音量変更失敗", error=str(e))
            outputs.append(target.video)
        return outputs

    def _group_assets(
        self, assets: List[VideoAsset]
    ) -> Dict[Tuple[datetime.date, datetime.time, str, str], List[VideoAsset]]:
        """録画済み動画を時刻帯ごとにグループ化する。"""
        groups: Dict[
            Tuple[datetime.date, datetime.time, str, str], List[VideoAsset]
        ] = defaultdict(list)
        for asset in assets:
            if asset.metadata is None:
                logger.warning(
                    "メタデータ未設定の動画を検出", video=str(asset.video)
                )
                continue

            started_at = asset.metadata.started_at
            file_date = started_at.date()
            file_time = started_at.time()

            result = asset.metadata.result
            if isinstance(result, BattleResult):
                match_name = str(result.match)
                rule_name = str(result.rule)
            elif isinstance(result, SalmonResult):
                match_name = "salmon"
                rule_name = str(result.stage)
            else:
                match_name = "unknown"
                rule_name = "unknown"

            for start, end in self.TIME_RANGES:
                if start < end:
                    if start <= file_time < end:
                        key = (file_date, start, match_name, rule_name)
                        groups[key].append(asset)
                        break
                else:
                    if file_time >= start or file_time < end:
                        adjusted_date = (
                            file_date
                            if file_time >= start
                            else file_date - datetime.timedelta(days=1)
                        )
                        key = (adjusted_date, start, match_name, rule_name)
                        groups[key].append(asset)
                        break
        return groups

    def _generate_title_and_description(
        self,
        assets: List[VideoAsset],
        day: datetime.date,
        time_slot: datetime.time,
        match: str,
        rule: str,
    ) -> Tuple[str, str]:
        """テンプレートに基づきタイトルと説明を生成する。"""
        settings = AppSettings.load_from_toml(Path("config/settings.toml"))
        yt = settings.youtube

        first = assets[0].metadata.result if assets[0].metadata else None

        if isinstance(first, SalmonResult):
            total_gold = sum(
                r.golden_egg
                for a in assets
                if (r := a.metadata.result) and isinstance(r, SalmonResult)
            )
            stages = ",".join(
                {
                    r.stage.value
                    for a in assets
                    if (r := a.metadata.result) and isinstance(r, SalmonResult)
                }
            )
            title = f"サーモンラン {stages}"
            description = f"金イクラ合計: {total_gold}"
            return title, description

        win = 0
        lose = 0
        chapters = ""
        elapsed = 0
        last_rate: RateBase | None = None

        for asset in assets:
            res = asset.metadata.result if asset.metadata else None
            if isinstance(res, BattleResult):
                win += 1 if res.kill >= res.death else 0
                lose += 1 if res.kill < res.death else 0
                tokens = {
                    "RESULT": "WIN" if res.kill >= res.death else "LOSE",
                    "KILL": res.kill,
                    "DEATH": res.death,
                    "SPECIAL": res.special,
                    "STAGE": res.stage.value,
                    "START_TIME": asset.metadata.started_at.strftime(
                        "%H:%M:%S"
                    ),
                }
                chapters += f"{elapsed:02d}:00 {yt.chapter_template.format(**tokens)}\n"
            elapsed += int(asset.video.stat().st_mtime)
            if asset.metadata.rate and asset.metadata.rate != last_rate:
                chapters += (
                    f"{asset.metadata.rate.label}: {asset.metadata.rate}\n"
                )
                last_rate = asset.metadata.rate

        rate = last_rate.short_str() if last_rate else ""
        tokens = {
            "BATTLE": match,
            "RULE": rule,
            "RATE": rate,
            "WIN": win,
            "LOSE": lose,
            "DAY": day.strftime("'%y.%m.%d"),
            "SCHEDULE": time_slot.strftime("%H").lstrip("0"),
            "CHAPTERS": chapters,
        }
        title = yt.title_template.format(**tokens) if yt.title_template else ""
        description = (
            yt.description_template.format(**tokens)
            if yt.description_template
            else ""
        )
        return title, description

    def _create_thumbnail(self, assets: List[VideoAsset]) -> Path | None:
        """明るいサムネイルを選び文字を描画する。"""
        image = self._select_bright_thumbnail(assets)
        if image is None:
            return None

        result = assets[0].metadata.result if assets[0].metadata else None
        if isinstance(result, BattleResult):
            win = sum(
                1
                for a in assets
                if isinstance(a.metadata.result, BattleResult)
                and a.metadata.result.kill >= a.metadata.result.death
            )
            lose = len(assets) - win
            info = {
                "win": win,
                "lose": lose,
                "rule": str(result.rule),
            }
        elif isinstance(result, SalmonResult):
            total = sum(
                r.golden_egg
                for a in assets
                if (r := a.metadata.result) and isinstance(r, SalmonResult)
            )
            info = {
                "stage": result.stage.value,
                "hazard": result.hazard,
                "gold": total,
            }
        else:
            info = {}

        image = self._design_thumbnail(image, info)
        out = assets[0].video.with_suffix(".thumb.png")
        try:
            image.save(out)
        except Exception as e:  # pragma: no cover - エラー時は警告のみ
            logger.warning("サムネイル保存失敗", error=str(e))
            return None
        return out

    # ----- 画像処理補助メソッド -----

    def _get_asset_path(self, name: str) -> Path:
        return self.THUMBNAIL_ASSETS_DIR / name

    def _load_font(self, name: str, size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(str(self._get_asset_path(name)), size)
        except Exception:
            return ImageFont.load_default()

    def _draw_text_with_outline(
        self,
        draw: ImageDraw.ImageDraw,
        pos: tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        outline: str = "black",
        fill: str = "white",
    ) -> None:
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                draw.text(
                    (pos[0] + dx, pos[1] + dy), text, font=font, fill=outline
                )
        draw.text(pos, text, font=font, fill=fill)

    def _select_bright_thumbnail(
        self, assets: List[VideoAsset]
    ) -> Image.Image | None:
        best_img = None
        best_score = -1.0
        for asset in assets:
            if not asset.thumbnail or not asset.thumbnail.exists():
                continue
            try:
                img = Image.open(asset.thumbnail).convert("RGB")
            except Exception as e:  # pragma: no cover - 読み込み失敗
                logger.warning(
                    "サムネイル読み込み失敗",
                    path=str(asset.thumbnail),
                    error=str(e),
                )
                continue
            v = np.array(img.convert("HSV"))[:, :, 2].astype(np.float32)
            score = float(np.mean(np.sort(v.flatten())[-100:]))
            if score > best_score:
                best_score = score
                best_img = img
        return best_img

    def _design_thumbnail(self, image: Image.Image, info: dict) -> Image.Image:
        draw = ImageDraw.Draw(image)
        font = self._load_font("Paintball_Beta.otf", 80)
        if "win" in info:
            text = f"{info['win']} - {info['lose']}"
            self._draw_text_with_outline(
                draw, (30, 20), text, font, fill="yellow"
            )
            self._draw_text_with_outline(draw, (30, 110), info["rule"], font)
        elif "stage" in info:
            self._draw_text_with_outline(
                draw, (30, 20), "サーモンラン", font, fill="orange"
            )
            self._draw_text_with_outline(
                draw,
                (30, 110),
                f"{info['stage']} {info['hazard']}%",
                font,
            )
            self._draw_text_with_outline(
                draw,
                (30, 200),
                f"金イクラ {info['gold']}",
                font,
            )
        return image

    def merge_clips(self, clips: list[VideoClip]) -> VideoClip:
        """複数のクリップを結合して新しいクリップを作成する。"""
        logger.info("クリップ結合", clips=[c.path.name for c in clips])
        raise NotImplementedError

    def embed_metadata(self, clip: VideoClip, match: Play) -> None:
        """メタデータを動画に書き込む。"""
        logger.info("メタデータ書き込み", clip=str(clip.path))
        raise NotImplementedError

    def adjust_volume(self, clip: VideoClip, config) -> None:
        """音量を調整する。"""
        logger.info("音量調整", clip=str(clip.path))
        raise NotImplementedError

    def generate_thumbnail(self, clip: VideoClip) -> Path:
        """サムネイル画像を生成する。"""
        logger.info("サムネイル生成", clip=str(clip.path))
        raise NotImplementedError

    def embed_subtitle(self, clip: VideoClip, subtitle: Path) -> None:
        """字幕を動画に埋め込む。"""
        logger.info(
            "字幕埋め込み", clip=str(clip.path), subtitle=str(subtitle)
        )
        raise NotImplementedError
