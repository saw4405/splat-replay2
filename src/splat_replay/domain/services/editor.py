"""動画編集サービス。"""

from __future__ import annotations

from pathlib import Path
import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import srt

from splat_replay.application.interfaces import VideoEditorPort
from splat_replay.infrastructure.adapters.ffmpeg_processor import FFmpegProcessor
from splat_replay.domain.models import (
    VideoAsset,
    BattleResult,
    SalmonResult,
    RateBase,
)
from splat_replay.shared.config import VideoEditSettings
from splat_replay.shared.logger import get_logger

logger = get_logger()


class VideoEditor(VideoEditorPort):
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

    def __init__(self, ffmpeg: FFmpegProcessor, settings: VideoEditSettings) -> None:
        self.ffmpeg = ffmpeg
        self.settings = settings

    def process(self, assets: List[VideoAsset]) -> Tuple[List[Path], List[VideoAsset]]:
        """複数の動画をまとめて編集する."""
        groups = self._group_assets(assets)
        outputs: List[Path] = []
        edited_assets: List[VideoAsset] = []

        for key, group in groups.items():
            if not group:
                continue

            day, time_slot, match_name, rule_name = key
            ext = group[0].video.suffix
            filename = f"{day.strftime('%Y%m%d')}_{time_slot.strftime('%H')}_{match_name}_{rule_name}{ext}"
            target = group[0].video.with_name(filename)

            if len(group) > 1:
                self.ffmpeg.merge([a.video for a in group], target)
            else:
                target.write_bytes(group[0].video.read_bytes())

            combined_subtitles = self._combine_subtitles(group)
            combined_srt = srt.compose(combined_subtitles)
            try:
                self.ffmpeg.embed_subtitle(target, combined_srt)
            except Exception as e:  # pragma: no cover - 埋め込み失敗は警告のみ
                logger.warning("字幕埋め込み失敗", error=str(e))

            title, description = self._generate_title_and_description(
                group,
                day,
                time_slot,
            )
            logger.info("タイトル生成", title=title)
            logger.debug("説明生成", description=description)
            try:
                metadata = {
                    "title": title,
                    "comment": description,
                }
                self.ffmpeg.embed_metadata(target, metadata)
            except Exception as e:  # pragma: no cover - 埋め込み失敗は警告のみ
                logger.warning("メタデータ埋め込み失敗", error=str(e))

            thumb = self._create_thumbnail(group)
            if thumb:
                logger.info("サムネイル生成", thumbnail=str(thumb))
                try:
                    thumb_data = thumb.read_bytes()
                    self.ffmpeg.embed_thumbnail(target, thumb_data)
                except Exception as e:  # pragma: no cover
                    logger.warning("サムネイル埋め込み失敗", error=str(e))
                finally:
                    thumb.unlink(missing_ok=True)

            if self.settings.volume_multiplier != 1.0:
                try:
                    self.ffmpeg.change_volume(
                        target, self.settings.volume_multiplier)
                except Exception as e:  # pragma: no cover
                    logger.warning("音量変更失敗", error=str(e))

            outputs.append(target)
            edited_assets.extend(group)
        return outputs, edited_assets

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
    ) -> Tuple[str, str]:
        """テンプレートに基づきタイトルと説明を生成する。"""
        first = assets[0].metadata.result if assets[0].metadata else None

        if isinstance(first, SalmonResult):
            total_gold = sum(
                r.golden_egg
                for a in assets
                if a.metadata and (r := a.metadata.result) and isinstance(r, SalmonResult)
            )
            stages = ",".join(
                {
                    r.stage.value
                    for a in assets
                    if a.metadata and (r := a.metadata.result) and isinstance(r, SalmonResult)
                }
            )
            title = f"サーモンラン {stages}"
            description = f"金イクラ合計: {total_gold}"
            return title, description

        def format_seconds(seconds: float) -> str:
            total_seconds = int(seconds)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"

        win = 0
        lose = 0
        chapters = ""
        elapsed = 0.0
        last_rate: RateBase | None = None

        for asset in assets:
            if asset.metadata and (res := asset.metadata.result) and isinstance(res, BattleResult):
                win += 1 if asset.metadata.judgement == "win" else 0
                lose += 1 if asset.metadata.judgement == "lose" else 0
                tokens = {
                    "RESULT": asset.metadata.judgement.upper() if asset.metadata.judgement else "UNKNOWN",
                    "KILL": res.kill,
                    "DEATH": res.death,
                    "SPECIAL": res.special,
                    "STAGE": res.stage.value,
                    "START_TIME": asset.metadata.started_at.strftime(
                        "%H:%M:%S"
                    ),
                }
                chapters += f"{format_seconds(elapsed)} {self.settings.chapter_template.format(**tokens) if self.settings.chapter_template else ''}\n"
            elapsed += self._get_video_length(asset.video)

            if asset.metadata and asset.metadata.rate and asset.metadata.rate != last_rate:
                chapters += (
                    f"{asset.metadata.rate.label}: {asset.metadata.rate}\n"
                )
                last_rate = asset.metadata.rate

        rate = last_rate.short_str() if last_rate else ""
        tokens = {
            "BATTLE": first.match.value if first else "Unknown",
            "RULE": first.rule.value if first else "Unknown",
            "RATE": rate,
            "WIN": win,
            "LOSE": lose,
            "DAY": day.strftime("'%y.%m.%d"),
            "SCHEDULE": time_slot.strftime("%H").lstrip("0"),
            "CHAPTERS": chapters,
        }
        title = self.settings.title_template.format(
            **tokens) if self.settings.title_template else ""
        description = (
            self.settings.description_template.format(**tokens)
            if self.settings.description_template
            else ""
        )
        return title, description

    def _create_thumbnail(self, assets: List[VideoAsset]) -> Path | None:
        """明るいサムネイルを選び文字を描画する。"""
        image = self._select_bright_thumbnail(assets)
        if image is None:
            return None

        result = assets[0].metadata.result if assets[0].metadata else None

        # サーモンランは未対応
        if result is None or isinstance(result, SalmonResult):
            return None

        win_count = sum(
            1
            for a in assets
            if a.metadata and isinstance(a.metadata.result, BattleResult)
            and a.metadata.judgement == "win"
        )
        lose_count = sum(
            1
            for a in assets
            if a.metadata and isinstance(a.metadata.result, BattleResult)
            and a.metadata.judgement == "lose"
        )
        match_name = result.match.value
        rule_name = result.rule.value
        rates = [a.metadata.rate for a in assets if a.metadata and a.metadata.rate]
        if len(rates) == 0:
            rate = None
        else:
            min_rate = min(rates)
            max_rate = max(rates)
            rate_prefix = f"{min_rate.label}: " if match_name == "Xマッチ" else ""
            if min_rate == max_rate:
                rate = f"{rate_prefix}{min_rate}"
            else:
                rate = f"{rate_prefix}{min_rate} ~ {max_rate}"
        stages = [
            a.metadata.result.stage.value
            for a in assets
            if a.metadata and isinstance(a.metadata.result, BattleResult)
        ]
        stages = list(dict.fromkeys(stages))
        stage1 = stages[0] if len(stages) > 0 else None
        stage2 = stages[1] if len(stages) > 1 else None

        image = self._design_thumbnail(
            image, win_count, lose_count, match_name, rule_name, rate, stage1, stage2
        )
        out = assets[0].video.with_suffix(".thumb.png")
        try:
            image.save(out)
        except Exception as e:  # pragma: no cover - エラー時は警告のみ
            logger.warning("サムネイル保存失敗", error=str(e))
            return None
        return out

    def _get_asset_path(self, name: str) -> Path:
        return self.THUMBNAIL_ASSETS_DIR / name

    def _load_font(self, name: str, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(str(self._get_asset_path(name)), size)

    def _draw_text_with_outline(self, draw: ImageDraw.ImageDraw, position: Tuple[int, int], text: str, font: ImageFont.FreeTypeFont, outline_color: str, fill_color: str):
        offsets = [(-5, 0), (5, 0), (0, -5), (0, 5),
                   (-5, -5), (-5, 5), (5, -5), (5, 5)]
        for dx, dy in offsets:
            draw.text((position[0]+dx, position[1]+dy),
                      text, fill=outline_color, font=font)
        draw.text(position, text, fill=fill_color, font=font)

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
                img_hsv = img.convert("HSV")
            except Exception as e:  # pragma: no cover - 読み込み失敗
                logger.warning(
                    "サムネイル読み込み失敗",
                    path=str(asset.thumbnail),
                    error=str(e),
                )
                continue
            width, height = img_hsv.size
            cropped_image = img_hsv.crop((0, 0, min(750, width), height))
            pixel_array = np.array(cropped_image)
            v_channel = pixel_array[:, :, 2]
            flat_pixels = v_channel.flatten()
            num_pixels = len(flat_pixels)
            n_top = max(1, int(num_pixels * 0.2))
            top_pixels = np.sort(flat_pixels)[-n_top:]
            score = np.mean(top_pixels)
            if score > best_score:
                best_score = score
                best_img = img
        return best_img

    def _design_thumbnail(self, thumbnail: Image.Image, win_count: int, lose_count: int, battle: str, rule: str, rate: Optional[str], stage1: Optional[str], stage2: Optional[str]) -> Image.Image:
        draw = ImageDraw.Draw(thumbnail)
        # 不要なステージ部分を塗りつぶし
        draw.rounded_rectangle((777, 21, 1849, 750), radius=40,
                               fill=(28, 28, 28), outline=(28, 28, 28), width=1)

        # 勝敗数を追加
        win_lose = f"{win_count} - {lose_count}"
        font = self._load_font("Paintball_Beta.otf", 120)
        bbox = draw.textbbox((0, 0), win_lose, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        centered_position = (int(458 - text_width // 2),
                             int(100 - text_height // 2))
        self._draw_text_with_outline(
            draw, centered_position, win_lose, font, outline_color="black", fill_color="yellow")

        # バトルのアイコンを追加
        battle_name = battle.split("(")[0]
        battle_path = self._get_asset_path(f"{battle_name}.png")
        if battle_path.exists():
            battle_image = Image.open(battle_path).convert("RGBA")
            battle_image = battle_image.resize((300, 300))
            thumbnail.paste(battle_image, (800, 40), battle_image)
        else:
            logger.warning(f"バトルアイコンが見つかりません: {battle_name}")

        # ルールの文字を追加
        font = self._load_font("ikamodoki1.ttf", 140)
        draw.text((1120, 50), rule, fill="white", font=font)

        # ルールのアイコンを追加
        rule_path = self._get_asset_path(f"{rule}.png")
        if rule_path.exists():
            rule_image = Image.open(rule_path).convert("RGBA")
            rule_image = rule_image.resize((150, 150))
            thumbnail.paste(rule_image, (1660, 70), rule_image)
        else:
            logger.warning(f"ルールアイコンが見つかりません: {rule}")

        # レートの文字を追加
        if rate:
            text_color = (1, 249, 196) if battle == "Xマッチ" else (
                250, 97, 0) if battle.startswith("バンカラマッチ") else "white"
            font = self._load_font("Paintball_Beta.otf", 70)
            draw.text((1125, 230), rate, fill=text_color, font=font)

        # ステージ画像を追加
        if stage1:
            stage1_path = self._get_asset_path(f"{stage1}.png")
            if stage1_path.exists():
                stage1_image = Image.open(stage1_path).convert("RGBA")
                stage1_image = stage1_image.resize((960, 168))
                thumbnail.paste(stage1_image, (860, 360), stage1_image)
            else:
                logger.warning(f"ステージ画像が見つかりません: {stage1}")
        else:
            logger.warning("ステージを検出できていません")

        if stage2:
            stage2_path = self._get_asset_path(f"{stage2}.png")
            if stage2_path.exists():
                stage2_image = Image.open(stage2_path).convert("RGBA")
                stage2_image = stage2_image.resize((960, 168))
                thumbnail.paste(stage2_image, (860, 540), stage2_image)
            else:
                logger.warning(f"ステージ画像が見つかりません: {stage2}")
        # 2つ目のステージがないことはあるので、警告は出さない

        overlay_path = self._get_asset_path("thumbnail_overlay.png")
        if overlay_path.exists():
            overlay_image = Image.open(overlay_path).convert("RGBA")
            thumbnail = Image.alpha_composite(thumbnail, overlay_image)

        return thumbnail

    def _combine_subtitles(self, assets: List[VideoAsset]):
        logger.info("字幕を結合します")
        combined_subtitles: List[srt.Subtitle] = []
        offset = datetime.timedelta(seconds=0)
        for asset in assets:
            if asset.subtitle and asset.subtitle.exists():
                srt_str = asset.subtitle.read_text(encoding="utf-8")
                subtitles = list(srt.parse(srt_str))
                if subtitles:
                    for subtitle in subtitles:
                        subtitle.start += offset
                        subtitle.end += offset
                    combined_subtitles.extend(subtitles)

            offset += datetime.timedelta(
                seconds=self._get_video_length(asset.video))
        return combined_subtitles

    def _get_video_length(self, video_path: Path) -> float:
        video = None
        try:
            video = cv2.VideoCapture(str(video_path.resolve()))
            if not video.isOpened():
                raise ValueError("動画ファイルが開けません")
            frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
            fps = video.get(cv2.CAP_PROP_FPS)
            length = frame_count / fps
            if length < 0:
                raise ValueError("動画の長さが不正です")
            return length
        except Exception as e:
            raise e
        finally:
            if video:
                video.release()
