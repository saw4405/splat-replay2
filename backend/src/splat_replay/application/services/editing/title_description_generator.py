"""タイトル・説明生成サービス。

責務: VideoAsset から YouTube アップロード用のタイトルと説明を生成する。
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from string import Formatter
from typing import Any, List, Literal, Tuple, cast

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


_TITLE_BRACKET_PAIRS: dict[str, str] = {
    "(": ")",
    "（": "）",
    "[": "]",
    "［": "］",
    "【": "】",
    "「": "」",
    "『": "』",
    "<": ">",
    "〈": "〉",
    "《": "》",
}


@dataclass
class _TemplateChunk:
    text: str
    kind: Literal["literal", "field"]
    empty_field: bool = False


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
        self.settings = self.config.get_video_edit_settings()
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
                    "MEDALS": self._format_medals(
                        res.gold_medals, res.silver_medals
                    ),
                    "STAGE": self._enum_value(res.stage),
                    "RATE": f"{asset.metadata.rate.label}{asset.metadata.rate}"
                    if asset.metadata.rate
                    else "",
                    "BATTLE": self._enum_value(res.match),
                    "RULE": self._enum_value(res.rule),
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
            match_name = self._enum_value(first.match, fallback="Unknown")
            rule_name = self._enum_value(first.rule, fallback="Unknown")

        stage_names = [
            a.metadata.result.stage.value
            for a in assets
            if (
                a.metadata
                and isinstance(a.metadata.result, BattleResult)
                and a.metadata.result.stage is not None
            )
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
            self._format_title_template(self.settings.title_template, tokens)
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
    def _enum_value(value: Enum | None, *, fallback: str = "UNKNOWN") -> str:
        return value.value if value is not None else fallback

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        """秒数を HH:MM:SS フォーマットに変換する。"""
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    @staticmethod
    def _format_title_template(
        template: str,
        tokens: dict[str, object],
    ) -> str:
        formatter = Formatter()
        format_args: tuple[Any, ...] = ()
        format_tokens = cast(dict[str, Any], tokens)
        chunks: list[_TemplateChunk] = []

        for (
            literal_text,
            field_name,
            format_spec,
            conversion,
        ) in formatter.parse(template):
            if literal_text:
                chunks.append(_TemplateChunk(literal_text, "literal"))
            if field_name is None:
                continue

            value, _ = formatter.get_field(
                field_name,
                format_args,
                format_tokens,
            )
            converted = formatter.convert_field(value, conversion)
            expanded_spec = formatter.vformat(
                cast(str, format_spec),
                format_args,
                format_tokens,
            )
            formatted = formatter.format_field(converted, expanded_spec)
            chunks.append(
                _TemplateChunk(
                    formatted,
                    "field",
                    value == "" or formatted.strip() == "",
                )
            )

        TitleDescriptionGenerator._remove_empty_bracketed_fields(chunks)
        return "".join(chunk.text for chunk in chunks)

    @staticmethod
    def _remove_empty_bracketed_fields(
        chunks: list[_TemplateChunk],
    ) -> None:
        for index, chunk in enumerate(chunks):
            if not chunk.empty_field:
                continue
            if index == 0 or index == len(chunks) - 1:
                continue

            previous_chunk = chunks[index - 1]
            next_chunk = chunks[index + 1]
            if (
                previous_chunk.kind != "literal"
                or next_chunk.kind != "literal"
            ):
                continue
            if not previous_chunk.text or not next_chunk.text:
                continue

            opening = previous_chunk.text[-1]
            closing = next_chunk.text[0]
            if _TITLE_BRACKET_PAIRS.get(opening) != closing:
                continue

            previous_chunk.text = previous_chunk.text[:-1]
            next_chunk.text = next_chunk.text[1:]
            chunk.text = ""

    @staticmethod
    def _format_medals(gold: int, silver: int) -> str:
        return f"🥇x{gold} 🥈x{silver}"
