from pathlib import Path
import datetime
from collections import defaultdict
from typing import Dict, List, Tuple

from splat_replay.shared.config import VideoEditSettings
from structlog.stdlib import BoundLogger
from splat_replay.domain.models import (
    VideoAsset,
    BattleResult,
    SalmonResult,
    RateBase,
    TIME_RANGES,
)
from splat_replay.application.interfaces import (
    VideoEditorPort,
    SubtitleEditorPort,
    ImageSelector,
)


class Editor:
    """動画編集処理を提供する。"""

    THUMBNAIL_ASSETS_DIR = Path("assets/thumbnail")

    def __init__(
        self,
        video_editor: VideoEditorPort,
        subtitle_editor: SubtitleEditorPort,
        image_selector: ImageSelector,
        settings: VideoEditSettings,
        logger: BoundLogger,
    ) -> None:
        self.video_editor = video_editor
        self.subtitle_editor = subtitle_editor
        self.image_selector = image_selector
        self.settings = settings
        self.logger = logger

    def process(
        self, assets: List[VideoAsset]
    ) -> Tuple[List[Path], List[VideoAsset]]:
        """複数の動画をまとめて編集する."""
        groups = self._group_assets(assets)

        outputs: List[Path] = []
        edited_assets: List[VideoAsset] = []
        for key, group in groups.items():
            if not group:
                continue
            day, time_slot, match_name, rule_name = key

            target = self._make_filename(
                group, day, time_slot, match_name, rule_name
            )
            self._merge_videos(target, group)
            self._embed_subtitle(target, group)
            self._embed_metadata(target, group, day, time_slot)
            self._embed_thumbnail(target, group)
            self._change_volume(target, self.settings.volume_multiplier)

            self.logger.info("動画編集完了", path=str(target))
            outputs.append(target)
            edited_assets.extend(group)
        return outputs, edited_assets

    def _make_filename(
        self,
        group: List[VideoAsset],
        day: datetime.date,
        time_slot: datetime.time,
        match_name: str,
        rule_name: str,
    ) -> Path:
        ext = group[0].video.suffix
        filename = f"{day.strftime('%Y%m%d')}_{time_slot.strftime('%H')}_{match_name}_{rule_name}{ext}"
        target = group[0].video.with_name(filename)
        return target

    def _merge_videos(self, target: Path, group: List[VideoAsset]):
        if len(group) > 1:
            self.video_editor.merge([a.video for a in group], target)
        else:
            target.write_bytes(group[0].video.read_bytes())

    def _embed_subtitle(self, target: Path, group: List[VideoAsset]):
        subtitles: List[Path] = []
        video_lengths: List[float] = []
        for asset in group:
            if not asset.subtitle or not asset.subtitle.exists():
                continue
            video_length = self.video_editor.get_video_length(asset.video)
            if video_length is None:
                self.logger.warning(
                    "動画の長さを取得できませんでした", video=str(asset.video)
                )
                continue
            subtitles.append(asset.subtitle)
            video_lengths.append(video_length)

        combined_srt = self.subtitle_editor.merge(subtitles, video_lengths)
        self.video_editor.embed_subtitle(target, combined_srt)

    def _embed_metadata(
        self,
        target: Path,
        group: List[VideoAsset],
        day: datetime.date,
        time_slot: datetime.time,
    ):
        title, description = self._generate_title_and_description(
            group,
            day,
            time_slot,
        )
        self.logger.info("タイトル生成", title=title)
        self.logger.debug("説明生成", description=description)
        metadata = {
            "title": title,
            "comment": description,
        }
        self.video_editor.embed_metadata(target, metadata)

    def _embed_thumbnail(self, target: Path, group: List[VideoAsset]):
        thumb = self._create_thumbnail(group)
        if not thumb or not thumb.exists():
            self.logger.warning("サムネイル生成に失敗しました")
            return

        self.logger.info("サムネイル生成", thumbnail=str(thumb))
        try:
            thumb_data = thumb.read_bytes()
            self.video_editor.embed_thumbnail(target, thumb_data)
        finally:
            thumb.unlink(missing_ok=True)

    def _change_volume(self, target: Path, multiplier: float):
        if self.settings.volume_multiplier == 1.0:
            return

        self.video_editor.change_volume(target, multiplier)

    def _group_assets(
        self, assets: List[VideoAsset]
    ) -> Dict[Tuple[datetime.date, datetime.time, str, str], List[VideoAsset]]:
        """録画済み動画を時刻帯ごとにグループ化する。"""
        groups: Dict[
            Tuple[datetime.date, datetime.time, str, str], List[VideoAsset]
        ] = defaultdict(list)
        for asset in assets:
            if asset.metadata is None:
                self.logger.warning(
                    "メタデータ未設定の動画を検出", video=str(asset.video)
                )
                continue

            started_at = asset.metadata.started_at
            file_date = started_at.date()
            file_time = started_at.time()

            result = asset.metadata.result
            if isinstance(result, BattleResult):
                match_name = result.match.value
                rule_name = result.rule.value
            elif isinstance(result, SalmonResult):
                match_name = "salmon"
                rule_name = result.stage.value
            else:
                match_name = "unknown"
                rule_name = "unknown"

            for start, end in TIME_RANGES:
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
        first = next(
            (
                a.metadata.result
                for a in assets
                if a.metadata and a.metadata.result
            ),
            None,
        )

        if isinstance(first, SalmonResult):
            total_gold = sum(
                r.golden_egg
                for a in assets
                if a.metadata
                and (r := a.metadata.result)
                and isinstance(r, SalmonResult)
            )
            stages = ",".join(
                {
                    r.stage.value
                    for a in assets
                    if a.metadata
                    and (r := a.metadata.result)
                    and isinstance(r, SalmonResult)
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
            if (
                asset.metadata
                and asset.metadata.rate
                and asset.metadata.rate != last_rate
            ):
                chapters += (
                    f"{asset.metadata.rate.label}: {asset.metadata.rate}\n"
                )
                last_rate = asset.metadata.rate

            if (
                asset.metadata
                and (res := asset.metadata.result)
                and isinstance(res, BattleResult)
            ):
                win += 1 if asset.metadata.judgement == "win" else 0
                lose += 1 if asset.metadata.judgement == "lose" else 0
                tokens = {
                    "RESULT": asset.metadata.judgement.upper()
                    if asset.metadata.judgement
                    else "UNKNOWN",
                    "KILL": res.kill,
                    "DEATH": res.death,
                    "SPECIAL": res.special,
                    "STAGE": res.stage.value,
                    "RATE": f"{asset.metadata.rate.label}{asset.metadata.rate}"
                    if asset.metadata.rate
                    else "",
                    "BATTLE": res.match.value,
                    "RULE": res.rule.value,
                    "DAY": day,
                    "SCHEDULE": time_slot,
                    "START_TIME": asset.metadata.started_at,
                }
                chapters += f"{format_seconds(elapsed)} {self.settings.chapter_template.format(**tokens) if self.settings.chapter_template else ''}\n"
            video_length = self.video_editor.get_video_length(asset.video)
            if video_length is not None:
                elapsed += video_length
            else:
                self.logger.warning(
                    "動画の長さを取得できませんでした", video=str(asset.video)
                )

        match_name = first.match.value if first else "Unknown"
        rule_name = first.rule.value if first else "Unknown"
        stages = [
            a.metadata.result.stage.value
            for a in assets
            if a.metadata and isinstance(a.metadata.result, BattleResult)
        ]
        stages = list(dict.fromkeys(stages))

        rates = [
            asset.metadata.rate
            for asset in assets
            if asset.metadata and asset.metadata.rate
        ]
        if len(rates) == 0:
            rate = ""
        else:
            max_rate = max(rates).short_str()
            min_rate = min(rates).short_str()
            rate_prefix = rates[0].label if match_name == "Xマッチ" else ""
            if min_rate == max_rate:
                rate = f"{rate_prefix}{min_rate}"
            else:
                rate = f"{rate_prefix}{min_rate}-{max_rate}"

        tokens = {
            "BATTLE": match_name,
            "RULE": rule_name,
            "RATE": rate,
            "WIN": win,
            "LOSE": lose,
            "DAY": day,
            "SCHEDULE": time_slot,
            "STAGES": ", ".join(stages),
            "CHAPTERS": chapters,
        }
        title = (
            self.settings.title_template.format(**tokens)
            if self.settings.title_template
            else ""
        )
        description = (
            self.settings.description_template.format(**tokens)
            if self.settings.description_template
            else ""
        )
        return title, description

    def _create_thumbnail(self, assets: List[VideoAsset]) -> Path | None:
        """明るいサムネイルを選び文字を描画する。"""
        # サーモンランは未対応
        result = assets[0].metadata.result if assets[0].metadata else None
        if result is None or isinstance(result, SalmonResult):
            return None

        thumbnails = [
            asset.thumbnail
            for asset in assets
            if asset.thumbnail and asset.thumbnail.exists()
        ]

        win_count = sum(
            1
            for a in assets
            if a.metadata
            and isinstance(a.metadata.result, BattleResult)
            and a.metadata.judgement == "win"
        )
        lose_count = sum(
            1
            for a in assets
            if a.metadata
            and isinstance(a.metadata.result, BattleResult)
            and a.metadata.judgement == "lose"
        )
        win_lose = f"{win_count} - {lose_count}"

        match_name = result.match.value
        match_name = match_name.split("(")[0]
        match_image_path = self._get_asset_path(f"{match_name}.png")

        rule_name = result.rule.value
        rule_image_path = self._get_asset_path(f"{rule_name}.png")

        rates = [
            a.metadata.rate for a in assets if a.metadata and a.metadata.rate
        ]
        if len(rates) == 0:
            rate = None
        else:
            min_rate = min(rates)
            max_rate = max(rates)
            rate_prefix = (
                f"{min_rate.label}: " if match_name == "Xマッチ" else ""
            )
            if min_rate == max_rate:
                rate = f"{rate_prefix}{min_rate}"
            else:
                rate = f"{rate_prefix}{min_rate} ~ {max_rate}"
        rate_text_color = (
            (1, 249, 196)
            if match_name == "Xマッチ"
            else (250, 97, 0)
            if match_name == "バンカラマッチ"
            else "white"
        )

        stages = [
            a.metadata.result.stage.value
            for a in assets
            if a.metadata and isinstance(a.metadata.result, BattleResult)
        ]
        stages = list(dict.fromkeys(stages))
        stage1 = stages[0] if len(stages) > 0 else None
        stage1_image_path = (
            self._get_asset_path(f"{stage1}.png") if stage1 else None
        )
        stage2 = stages[1] if len(stages) > 1 else None
        stage2_image_path = (
            self._get_asset_path(f"{stage2}.png") if stage2 else None
        )

        overlay_image_path = self._get_asset_path("thumbnail_overlay.png")

        font_paintball = str(self._get_asset_path("Paintball_Beta.otf"))
        font_ikamodoki = str(self._get_asset_path("ikamodoki1.ttf"))

        # 高スコア(キルレがいい)のサムネイルをスコアが高い順に格納
        high_score_thumbnails: list[tuple[float, Path]] = []
        for asset in assets:
            if (
                asset.metadata is None
                or not isinstance(asset.metadata.result, BattleResult)
                or asset.thumbnail is None
            ):
                continue
            kill = asset.metadata.result.kill
            death = asset.metadata.result.death
            score = kill - death * 1.25
            if score > 5:
                high_score_thumbnails.append((score, asset.thumbnail))
                self.logger.info("高スコアの動画を検出", score=score,
                                 kill=kill, death=death)
        high_score_thumbnails.sort(reverse=True, key=lambda x: x[0])
        high_score_thumbnails = high_score_thumbnails[:3]

        out = assets[0].video.with_suffix(".thumb.png")
        (
            self.image_selector(thumbnails, (0, 0, 750, 1.0))
            .draw_rounded_rectangle(
                (777, 20, 1850, 750),
                radius=40,
                fill_color=(28, 28, 28),
                outline_color=(28, 28, 28),
                outline_width=1,
            )
            .draw_text_with_outline(
                win_lose,
                (458, 100),
                font_paintball,
                120,
                fill_color="yellow",
                outline_color="black",
                outline_width=5,
                center=True,
            )
            .draw_image(match_image_path, (800, 40), size=(300, 300))
            .draw_text(
                rule_name, (1120, 50), font_ikamodoki, 140, fill_color="white"
            )
            .draw_image(rule_image_path, (1660, 70), size=(150, 150))
            .when(rate is not None, lambda d: d.draw_text(
                rate, (1125, 230), font_paintball, 70, fill_color=rate_text_color
            ))
            .when(stage1_image_path is not None and stage1_image_path.exists(),
                  lambda d: d.draw_image(
                stage1_image_path, (860, 360), size=(960, 168)
            ))
            .when(stage2_image_path is not None and stage2_image_path.exists(),
                  lambda d: d.draw_image(
                stage2_image_path, (860, 540), size=(960, 168)
            ))
            .for_each(
                list(enumerate(high_score_thumbnails)),
                lambda item, d: d.draw_image(
                    item[1][1],
                    (
                        0 + (item[0] // 3) * (146 * 2 + 30),
                        620 + (item[0] % 3) * (60 * 2 + 30)
                    ),
                    crop=(1467, 259, 1661, 319),
                    size=(146 * 2, 60 * 2),
                ) if item[1][1].exists() else d
            )
            .when(
                overlay_image_path.exists(),
                lambda d: d.overlay_image(overlay_image_path)
            )
            .save(out)
        )
        return out

    def _get_asset_path(self, name: str) -> Path:
        return self.THUMBNAIL_ASSETS_DIR / name
