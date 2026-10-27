"""サムネイル生成サービス。

責務: VideoAsset からサムネイル画像を生成する。
"""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import List
from contextlib import nullcontext

from splat_replay.application.interfaces.thumbnail_design import (
    ThumbnailAssetsPort,
    ThumbnailBounds,
)
from splat_replay.domain.config.video_edit import ThumbnailDesign
from .thumbnail_design_renderer import ThumbnailContent, render_design

from splat_replay.application.interfaces import (
    FileSystemPort,
    ImageSelector,
    LoggerPort,
    PathsPort,
    ThumbnailRuleImageResolverPort,
)
from splat_replay.domain.models import (
    BattleResult,
    Judgement,
    Match,
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
        rule_image_resolver: ThumbnailRuleImageResolverPort,
        thumbnail_assets: ThumbnailAssetsPort | None = None,
    ) -> None:
        self._thumbnail_assets = thumbnail_assets
        self.logger = logger
        self.paths = paths
        self.image_selector = image_selector
        self._file_system = file_system
        self._rule_image_resolver = rule_image_resolver

    def create(
        self,
        assets: List[VideoAsset],
        design: ThumbnailDesign | None = None,
        layout: dict[str, ThumbnailBounds] | None = None,
    ) -> Path | None:
        if not assets:
            return None
        result = assets[0].metadata.result if assets[0].metadata else None
        if result is None or isinstance(result, SalmonResult):
            return None
        lease = (
            self._thumbnail_assets.lease(design)
            if self._thumbnail_assets
            else nullcontext(
                design
                or ThumbnailDesign.parse_raw(
                    self._file_system.read_bytes(
                        self.paths.get_thumbnail_asset("design.default.json")
                    )
                )
            )
        )
        with lease as snapshot:
            return self._create(assets, snapshot, layout)

    def _create(
        self,
        assets: List[VideoAsset],
        design: ThumbnailDesign,
        layout: dict[str, ThumbnailBounds] | None = None,
    ) -> Path | None:
        """明るいサムネイルを選び描画する。

        Returns:
            生成されたサムネイルのパス。生成できなかった場合は None。
        """
        # サーモンランは未対応
        result = assets[0].metadata.result if assets[0].metadata else None
        if result is None or isinstance(result, SalmonResult):
            return None
        if result.match is None or result.rule is None:
            self.logger.warning(
                "マッチまたはルールが未設定のためサムネイル生成をスキップしました"
            )
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

        # マッチ画像
        is_event_match = result.match is Match.CHALLENGE
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
        elif is_event_match:
            rate = f"Best Power: {max(rates)}"
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
            (241, 46, 125)
            if is_event_match
            else (1, 249, 196)
            if match_name == "Xマッチ"
            else (250, 97, 0)
            if match_name == "バンカラマッチ"
            else "white"
        )

        # ステージ画像
        stage_names = [
            a.metadata.result.stage.value
            for a in assets
            if (
                a.metadata
                and isinstance(a.metadata.result, BattleResult)
                and a.metadata.result.stage is not None
            )
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

        if design.background.source == "image":
            background_path = (
                self._thumbnail_assets.path(design.background.asset)
                if self._thumbnail_assets
                else self.paths.get_thumbnail_asset(design.background.asset)
            )
            drawer = self.image_selector([background_path], (0, 0, 1.0, 1.0))
            if drawer is not None:
                drawer.fit_background(
                    design.background.x,
                    design.background.y,
                    design.background.scale,
                )
        else:
            drawer = self.image_selector(thumbnails, (0, 0, 750, 1.0))
            if drawer is not None and (
                design.background.x != 0
                or design.background.y != 0
                or design.background.scale != 1
            ):
                drawer.fit_background(
                    design.background.x,
                    design.background.y,
                    design.background.scale,
                )
        if drawer is None:
            self.logger.warning(
                "元画像がないためサムネイル生成をスキップしました"
            )
            return None

        label_path = self.paths.get_thumbnail_asset(
            f"rule-labels/{result.rule.name.lower()}.png"
        )
        rule_label = self._rule_image_resolver.resolve(label_path)
        if rule_label is None and any(
            e.visible and e.source == "rule_label" for e in design.elements
        ):
            raise RuntimeError(
                f"ルール名画像が未配置または不正です: {label_path}"
            )
        rule_icon_exists = self._file_system.is_file(rule_image_path)
        if not rule_icon_exists:
            self.logger.warning(
                "ルール用アイコンがないため省略します",
                rule=rule_name,
                path=str(rule_image_path),
            )

        with tempfile.NamedTemporaryFile(
            dir=assets[0].video.parent,
            prefix=f"{assets[0].video.stem}.",
            suffix=".thumb.png",
            delete=False,
        ) as temporary:
            out = Path(temporary.name)

        rate_label = (
            "Best Power: "
            if is_event_match
            else f"{min(rates).label}: "
            if rates and match_name == "Xマッチ"
            else ""
        )
        rate_value = rate[len(rate_label) :] if rate else ""
        values: dict[str, str | int] = {
            "WIN": win_count,
            "LOSE": lose_count,
            "RATE": rate or "",
            "RATE_LABEL": rate_label if rate else "",
            "RATE_VALUE": rate_value,
            "RATE_MIN": str(min(rates)) if rates else "",
            "RATE_MAX": str(max(rates)) if rates else "",
            "BATTLE": result.match.value,
            "RULE": rule_name,
            "STAGES": " / ".join(unique_stage_names),
        }
        images: dict[str, list[Path]] = {
            "match": [match_image_path],
            "rule_label": [rule_label] if rule_label else [],
            "rule_icon": [rule_image_path] if rule_icon_exists else [],
            "stages": [
                p
                for p in (stage1_image_path, stage2_image_path)
                if p is not None and self._file_system.is_file(p)
            ],
            "highlights": [
                p
                for _, p in high_score_thumbnails
                if self._file_system.is_file(p)
            ],
        }
        color = (
            rate_text_color
            if isinstance(rate_text_color, str)
            else "#" + "".join(f"{c:02x}" for c in rate_text_color)
        )
        try:
            render_design(
                drawer,
                design,
                ThumbnailContent(values, images, color),
                self.paths,
                self._thumbnail_assets,
                self._file_system,
                layout,
            )
            drawer.save(out)
        except Exception:
            out.unlink(missing_ok=True)
            raise
        return out
