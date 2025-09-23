import datetime
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    ImageSelector,
    SubtitleEditorPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.domain.models import (
    TIME_RANGES,
    BattleResult,
    Judgement,
    RateBase,
    SalmonResult,
    VideoAsset,
)
from splat_replay.shared import paths
from splat_replay.shared.config import VideoEditSettings

from .progress import ProgressReporter


class AutoEditor:
    """録画済み動画の編集を行うサービス、"""

    def __init__(
        self,
        video_editor: VideoEditorPort,
        subtitle_editor: SubtitleEditorPort,
        image_selector: ImageSelector,
        settings: VideoEditSettings,
        repo: VideoAssetRepositoryPort,
        logger: BoundLogger,
        progress: ProgressReporter,
    ):
        self.repo = repo
        self.logger = logger
        self.video_editor = video_editor
        self.subtitle_editor = subtitle_editor
        self.image_selector = image_selector
        self.settings = settings
        self.progress = progress
        self._cancelled: bool = False

    def request_cancel(self) -> None:
        """Request cancellation; takes effect between groups/steps."""
        self._cancelled = True

    async def execute(self) -> list[Path]:
        self.logger.info("自動編集を開始します")
        edited: list[Path] = []

        assets = self.repo.list_recordings()
        groups = self._group_assets(assets)

        task_id = "auto_edit"
        items: list[str] = []
        for idx, (key, group) in enumerate(groups.items()):
            if not group:
                continue
            day, time_slot, match_name, rule_name = key
            items.append(
                f"{day.strftime('%m/%d')} {time_slot.strftime('%H')}時～ {match_name} {rule_name}"
            )
        self.progress.start_task(task_id, "自動編集", len(items), items=items)

        for idx, (key, group) in enumerate(groups.items()):
            if self._cancelled:
                self.progress.finish(
                    task_id, False, "自動編集をキャンセルしました"
                )
                self.logger.info("自動編集をキャンセルしました")
                return edited
            if not group:
                continue
            day, time_slot, match_name, rule_name = key
            label = f"{day.strftime('%m/%d')} {time_slot.strftime('%H')}時～ {match_name} {rule_name}"
            # 現在処理中のアイテムを明示 (GUI のタスクリスト更新用)
            self.progress.item_stage(
                task_id,
                idx,
                "edit_group",
                "グループ編集",
                message=label,
            )

            target = self._edit(
                idx, day, time_slot, match_name, rule_name, group
            )
            self.logger.info("動画編集を開始します", path=str(target))
            target = self.repo.save_edited(Path(target))
            for asset in group:
                self.logger.info(
                    "録画済み動画を削除します", path=str(asset.video)
                )
                self.repo.delete_recording(asset.video)
            # 保存ステップを通知し、全体の進捗を 1 進める
            self.progress.item_stage(
                task_id,
                idx,
                "save",
                "録画済動画削除・編集済動画保存",
                message=target.name,
            )
            self.progress.advance(task_id)
            edited.append(target)

        if self._cancelled:
            self.progress.finish(
                task_id, False, "自動編集をキャンセルしました"
            )
            self.logger.info("自動編集をキャンセルしました")
        else:
            self.progress.finish(task_id, True, "自動編集を完了しました")
        self.logger.info("自動編集を完了しました", edited=edited)
        return edited

    def _edit(
        self,
        idx: int,
        day: datetime.date,
        time_slot: datetime.time,
        match_name: str,
        rule_name: str,
        group: List[VideoAsset],
    ) -> Path:
        target = self._make_filename(
            group, day, time_slot, match_name, rule_name
        )
        task_id = "auto_edit"
        self.progress.item_stage(
            task_id,
            idx,
            "concat",
            "動画結合",
            message=f"{len(group)}本の動画を結合",
        )
        self._merge_videos(target, group)

        self.progress.item_stage(
            task_id,
            idx,
            "subtitle",
            "字幕編集",
        )
        self._embed_subtitle(target, group)

        self.progress.item_stage(
            task_id,
            idx,
            "metadata",
            "メタデータ編集",
        )
        self._embed_metadata(target, group, day, time_slot)

        self.progress.item_stage(
            task_id,
            idx,
            "thumbnail",
            "サムネイル編集",
        )
        self._embed_thumbnail(target, group)

        if self.settings.volume_multiplier != 1.0:
            self.progress.item_stage(
                task_id,
                idx,
                "volume",
                "音量調整",
                message=f"x{self.settings.volume_multiplier}",
            )
        self._change_volume(target, self.settings.volume_multiplier)
        return target

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

    def _merge_videos(self, target: Path, group: List[VideoAsset]) -> None:
        if len(group) > 1:
            self.video_editor.merge([a.video for a in group], target)
        else:
            target.write_bytes(group[0].video.read_bytes())

    def _embed_subtitle(self, target: Path, group: List[VideoAsset]) -> None:
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
    ) -> None:
        title, description = self._generate_title_and_description(
            group,
            day,
            time_slot,
        )
        self.logger.info("タイトル編集", title=title)
        self.logger.debug("説明編集", description=description)
        metadata = {
            "title": title,
            "comment": description,
        }
        self.video_editor.embed_metadata(target, metadata)

    def _embed_thumbnail(self, target: Path, group: List[VideoAsset]) -> None:
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

    def _change_volume(self, target: Path, multiplier: float) -> None:
        if self.settings.volume_multiplier == 1.0:
            return

        self.video_editor.change_volume(target, multiplier)

    def _group_assets(
        self, assets: List[VideoAsset]
    ) -> Dict[Tuple[datetime.date, datetime.time, str, str], List[VideoAsset]]:
        """録画済み動画を時刻帯ごとにグループ化する"""
        groups: Dict[
            Tuple[datetime.date, datetime.time, str, str], List[VideoAsset]
        ] = defaultdict(list)
        for asset in assets:
            if asset.metadata is None:
                self.logger.warning(
                    "メタデータ未設定の動画を検出しました",
                    video=str(asset.video),
                )
                continue
            if not asset.metadata.started_at:
                self.logger.warning(
                    "録画開始時刻が未設定の動画を検出しました",
                    video=str(asset.video),
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
        """タイトルと説明を生成する"""
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
                win += 1 if asset.metadata.judgement == Judgement.WIN else 0
                lose += 1 if asset.metadata.judgement == Judgement.LOSE else 0
                tokens = {
                    "RESULT": asset.metadata.judgement.value
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
        stage_names = [
            a.metadata.result.stage.value
            for a in assets
            if a.metadata and isinstance(a.metadata.result, BattleResult)
        ]
        unique_stages = list(dict.fromkeys(stage_names))

        rates: list[RateBase] = [
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
            "STAGES": ", ".join(unique_stages),
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
        """明るいサムネイルを選び描画する、"""
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
            and a.metadata.judgement == Judgement.WIN
        )
        lose_count = sum(
            1
            for a in assets
            if a.metadata
            and isinstance(a.metadata.result, BattleResult)
            and a.metadata.judgement == Judgement.LOSE
        )
        win_lose = f"{win_count} - {lose_count}"

        match_name = result.match.value
        match_name = match_name.split("(")[0]
        match_image_path = paths.thumbnail_asset(f"{match_name}.png")

        rule_name = result.rule.value
        rule_image_path = paths.thumbnail_asset(f"{rule_name}.png")

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

        stage_names = [
            a.metadata.result.stage.value
            for a in assets
            if a.metadata and isinstance(a.metadata.result, BattleResult)
        ]
        unique_stage_names = list(dict.fromkeys(stage_names))
        stage1 = unique_stage_names[0] if unique_stage_names else None
        stage1_image_path = (
            paths.thumbnail_asset(f"{stage1}.png") if stage1 else None
        )
        stage2 = unique_stage_names[1] if len(unique_stage_names) > 1 else None
        stage2_image_path = (
            paths.thumbnail_asset(f"{stage2}.png") if stage2 else None
        )

        overlay_image_path = paths.thumbnail_asset("thumbnail_overlay.png")

        font_paintball = str(paths.thumbnail_asset("Paintball_Beta.otf"))
        font_ikamodoki = str(paths.thumbnail_asset("ikamodoki1.ttf"))

        # 高スコア(キルレが高い)のサムネイルをスコアが高い順に格納する
        high_score_thumbnails: list[tuple[float, Path]] = []
        seen_kd: set[tuple[int, int]] = set()
        for asset in assets:
            if (
                asset.metadata is None
                or not isinstance(asset.metadata.result, BattleResult)
                or asset.thumbnail is None
            ):
                continue
            kill = asset.metadata.result.kill
            death = asset.metadata.result.death
            kd_pair = (kill, death)
            if kd_pair in seen_kd:
                continue
            score = kill - death * 1.25
            if score > 5.5:
                seen_kd.add(kd_pair)
                high_score_thumbnails.append((score, asset.thumbnail))
                self.logger.info(
                    "高スコアの動画を検出しました",
                    score=score,
                    kill=kill,
                    death=death,
                )
        high_score_thumbnails.sort(reverse=True, key=lambda x: x[0])
        high_score_thumbnails = high_score_thumbnails[:3]

        out = assets[0].video.with_suffix(".thumb.png")
        (
            self.image_selector(thumbnails, (0, 0, 750, 1.0))
            # 勝敗を記載
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
            # マッチルール・レート・ステージを描画するベース
            .draw_rounded_rectangle(
                (777, 20, 1850, 750),
                radius=40,
                fill_color=(28, 28, 28),
                outline_color=(28, 28, 28),
                outline_width=1,
            )
            # マッチを描画
            .draw_image(match_image_path, (800, 40), size=(300, 300))
            # ルールを記載し描画
            .draw_text(
                rule_name, (1120, 50), font_ikamodoki, 140, fill_color="white"
            )
            .draw_image(rule_image_path, (1660, 70), size=(150, 150))
            # レートを記載し描画
            .when(
                rate is not None,
                lambda d: d.draw_text(
                    rate,
                    (1125, 230),
                    font_paintball,
                    70,
                    fill_color=rate_text_color,
                ),
            )
            # ステージ画像を描画
            .when(
                stage1_image_path is not None and stage1_image_path.exists(),
                lambda d: d.draw_image(
                    stage1_image_path, (860, 360), size=(960, 168)
                ),
            )
            .when(
                stage2_image_path is not None and stage2_image_path.exists(),
                lambda d: d.draw_image(
                    stage2_image_path, (860, 540), size=(960, 168)
                ),
            )
            # 高キルレ画像を左下に描画
            .for_each(
                list(enumerate(high_score_thumbnails)),
                lambda item, d: d.draw_image(
                    item[1][1],
                    (
                        0 + (item[0] // 3) * (146 * 2 + 30),
                        620 + (item[0] % 3) * (60 * 2 + 30),
                    ),
                    crop=(1467, 259, 1661, 319),
                    size=(146 * 2, 60 * 2),
                )
                if item[1][1].exists()
                else d,
            )
            # キルレを白枠で囲う
            .for_each(
                list(enumerate(high_score_thumbnails)),
                lambda item, d: d.draw_rectangle(
                    (
                        int(0 + (item[0] // 3) * (146 * 2 + 30)),
                        int(620 + (item[0] % 3) * (60 * 2 + 30)),
                        int(0 + (item[0] // 3) * (146 * 2 + 30) + 146 * 2),
                        int(620 + (item[0] % 3) * (60 * 2 + 30) + 60 * 2),
                    ),
                    fill_color=None,
                    outline_color="white",
                    outline_width=3,
                )
                if item[1][1].exists()
                else d,
            )
            .when(
                overlay_image_path.exists(),
                lambda d: d.overlay_image(overlay_image_path),
            )
            .save(out)
        )
        return out
