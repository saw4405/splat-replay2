"""VideoAsset グループ化サービス。

責務: 録画済み動画を時刻帯・マッチ・ルールごとにグループ化する。
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from typing import Dict, List, Tuple

from splat_replay.application.interfaces import LoggerPort
from splat_replay.domain.models import (
    TIME_RANGES,
    BattleResult,
    SalmonResult,
    VideoAsset,
)


class VideoGroupingService:
    """VideoAsset を時刻帯・マッチ・ルールごとにグループ化する。"""

    def __init__(self, logger: LoggerPort):
        self.logger = logger

    def group_by_timeslot(
        self, assets: List[VideoAsset]
    ) -> Dict[Tuple[datetime.date, datetime.time, str, str], List[VideoAsset]]:
        """録画済み動画を時刻帯ごとにグループ化する。

        グループ化キー: (日付, 時刻帯, マッチ名, ルール名)
        """
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
                    # 通常の時間帯（例: 09:00-12:00）
                    if start <= file_time < end:
                        key = (file_date, start, match_name, rule_name)
                        groups[key].append(asset)
                        break
                else:
                    # 日をまたぐ時間帯（例: 21:00-03:00）
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
