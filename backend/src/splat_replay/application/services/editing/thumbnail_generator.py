"""サムネイル生成サービス。

責務: VideoAsset からサムネイル画像を生成する。
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from splat_replay.application.interfaces import (
    FileSystemPort,
    ImageSelector,
    LoggerPort,
    PathsPort,
)
from splat_replay.domain.models import (
    BattleResult,
    Judgement,
    SalmonResult,
    VideoAsset,
)


class ThumbnailGenerator:
    """サムネイルを生成するサービス。"""

    def __init__(
        self,
        logger: LoggerPort,
        paths: PathsPort,
        image_selector: ImageSelector,
        file_system: FileSystemPort,
    ):
        self.logger = logger
        self.paths = paths
        self.image_selector = image_selector
        self._file_system = file_system

    def create(self, assets: List[VideoAsset]) -> Path | None:
        """明るいサムネイルを選び描画する。

        Returns:
            生成されたサムネイルのパス。生成できなかった場合は None。
        """
        # サーモンランは未対応
        result = assets[0].metadata.result if assets[0].metadata else None
        if result is None or isinstance(result, SalmonResult):
            return None

        thumbnails = [
            asset.thumbnail
            for asset in assets
            if asset.thumbnail and self._file_system.is_file(asset.thumbnail)
        ]

        # 勝敗カウント
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

        # マッチ画像
        match_name = result.match.value
        match_name = match_name.split("(")[0]
        match_image_path = self.paths.get_thumbnail_asset(f"{match_name}.png")

        # ルール画像
        rule_name = result.rule.value
        rule_image_path = self.paths.get_thumbnail_asset(f"{rule_name}.png")

        # レート情報
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

        # ステージ画像
        stage_names = [
            a.metadata.result.stage.value
            for a in assets
            if a.metadata and isinstance(a.metadata.result, BattleResult)
        ]
        unique_stage_names = list(dict.fromkeys(stage_names))
        stage1 = unique_stage_names[0] if unique_stage_names else None
        stage1_image_path = (
            self.paths.get_thumbnail_asset(f"{stage1}.png") if stage1 else None
        )
        stage2 = unique_stage_names[1] if len(unique_stage_names) > 1 else None
        stage2_image_path = (
            self.paths.get_thumbnail_asset(f"{stage2}.png") if stage2 else None
        )

        stage1_image_exists = (
            stage1_image_path is not None
            and self._file_system.is_file(stage1_image_path)
        )
        stage2_image_exists = (
            stage2_image_path is not None
            and self._file_system.is_file(stage2_image_path)
        )

        overlay_image_path = self.paths.get_thumbnail_asset(
            "thumbnail_overlay.png"
        )

        font_paintball = str(
            self.paths.get_thumbnail_asset("Paintball_Beta.otf")
        )
        font_ikamodoki = str(self.paths.get_thumbnail_asset("ikamodoki1.ttf"))

        # 高スコア（キルレが高い）のサムネイルをスコアが高い順に格納する
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
                stage1_image_exists,
                lambda d: d.draw_image(
                    stage1_image_path, (860, 360), size=(960, 168)
                ),
            )
            .when(
                stage2_image_exists,
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
                if self._file_system.is_file(item[1][1])
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
                if self._file_system.is_file(item[1][1])
                else d,
            )
            .when(
                self._file_system.is_file(overlay_image_path),
                lambda d: d.overlay_image(overlay_image_path),
            )
            .save(out)
        )
        return out
