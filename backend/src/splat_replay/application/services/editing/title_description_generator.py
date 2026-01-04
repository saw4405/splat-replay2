"""タイトル・説明生成サービス。

責務: VideoAsset から YouTube アップロード用のタイトルと説明を生成する。
"""

from __future__ import annotations

import datetime
from typing import List, Tuple

from splat_replay.application.interfaces import (
    ConfigPort,
    LoggerPort,
    VideoEditorPort,
)
from splat_replay.domain.models import (
    BattleResult,
    Judgement,
    RateBase,
    SalmonResult,
    VideoAsset,
)


class TitleDescriptionGenerator:
    """タイトルと説明を生成するサービス。"""

    def __init__(
        self,
        logger: LoggerPort,
        config: ConfigPort,
        video_editor: VideoEditorPort,
    ):
        self.logger = logger
        self.config = config
        self.settings = config.get_video_edit_settings()
        self.video_editor = video_editor

    async def generate(
        self,
        assets: List[VideoAsset],
        day: datetime.date,
        time_slot: datetime.time,
    ) -> Tuple[str, str]:
        """タイトルと説明を生成する。

        Returns:
            (title, description)
        """
        first = next(
            (
                a.metadata.result
                for a in assets
                if a.metadata and a.metadata.result
            ),
            None,
        )

        # サーモンランの場合
        if isinstance(first, SalmonResult):
            return await self._generate_salmon(assets)

        # バトルの場合
        return await self._generate_battle(assets, day, time_slot, first)

    async def _generate_salmon(
        self, assets: List[VideoAsset]
    ) -> Tuple[str, str]:
        """サーモンラン用のタイトルと説明を生成する。"""
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

    async def _generate_battle(
        self,
        assets: List[VideoAsset],
        day: datetime.date,
        time_slot: datetime.time,
        first: BattleResult | SalmonResult | None,
    ) -> Tuple[str, str]:
        """バトル用のタイトルと説明を生成する。"""
        win = 0
        lose = 0
        chapters = ""
        elapsed = 0.0
        last_rate: RateBase | None = None

        for asset in assets:
            # レート変更があればチャプターに追加
            if (
                asset.metadata
                and asset.metadata.rate
                and asset.metadata.rate != last_rate
            ):
                chapters += (
                    f"{asset.metadata.rate.label}: {asset.metadata.rate}\n"
                )
                last_rate = asset.metadata.rate

            # 勝敗カウント
            if (
                asset.metadata
                and (res := asset.metadata.result)
                and isinstance(res, BattleResult)
            ):
                win += 1 if asset.metadata.judgement == Judgement.WIN else 0
                lose += 1 if asset.metadata.judgement == Judgement.LOSE else 0

                # チャプター生成
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
                chapters += f"{self._format_seconds(elapsed)} {self.settings.chapter_template.format(**tokens) if self.settings.chapter_template else ''}\n"

            # 動画の長さを累積
            video_length = await self.video_editor.get_video_length(
                asset.video
            )
            if video_length is not None:
                elapsed += video_length
            else:
                self.logger.warning(
                    "動画の長さを取得できませんでした", video=str(asset.video)
                )

        # タイトル・説明のトークン生成
        match_name = "Unknown"
        rule_name = "Unknown"
        if first and isinstance(first, BattleResult):
            match_name = first.match.value
            rule_name = first.rule.value

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

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        """秒数を HH:MM:SS フォーマットに変換する。"""
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"
