"""自動編集ユースケース。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, time, date
from pathlib import Path

from splat_replay.application.interfaces import (
    VideoEditorPort,
    VideoAssetRepository,
)
from splat_replay.domain.models import VideoAsset, BattleResult
from splat_replay.infrastructure.adapters.ffmpeg_processor import (
    FFmpegProcessor,
)
from splat_replay.shared.logger import get_logger


class AutoEditUseCase:
    """録画済み動画を検索して編集を行う。"""

    # スケジュール時間帯 (日をまたぐ区間含む)
    TIME_RANGES: list[tuple[time, time]] = [
        (time(1, 0), time(3, 0)),
        (time(3, 0), time(5, 0)),
        (time(5, 0), time(7, 0)),
        (time(7, 0), time(9, 0)),
        (time(9, 0), time(11, 0)),
        (time(11, 0), time(13, 0)),
        (time(13, 0), time(15, 0)),
        (time(15, 0), time(17, 0)),
        (time(17, 0), time(19, 0)),
        (time(19, 0), time(21, 0)),
        (time(21, 0), time(23, 0)),
        (time(23, 0), time(1, 0)),
    ]

    def __init__(
        self,
        editor: VideoEditorPort,
        ffmpeg: FFmpegProcessor,
        repo: VideoAssetRepository,
    ) -> None:
        self.editor = editor
        self.ffmpeg = ffmpeg
        self.repo = repo
        self.logger = get_logger()

    def _collect_assets(self) -> list[VideoAsset]:
        return self.repo.list_recordings()

    def _group_assets(
        self, assets: list[VideoAsset]
    ) -> dict[tuple[date, time, str, str], list[VideoAsset]]:
        """動画アセットをグループ分けする。"""
        from collections import defaultdict
        import datetime as dtmod

        groups: dict[
            tuple[date, time, str, str], list[VideoAsset]
        ] = defaultdict(list)
        for asset in assets:
            if asset.metadata is None:
                self.logger.warning(
                    "メタデータがない動画を検出",
                    video=asset.video.name,
                )
                continue
            # バトル以外は未実装
            if not isinstance(asset.metadata.result, BattleResult):
                self.logger.warning(
                    "BattleResultではないメタデータを検出",
                    video=asset.video.name,
                )
                continue
            started_at = asset.metadata.started_at
            file_date = started_at.date()
            file_time = started_at.time()
            match_name = (
                str(asset.metadata.result.match)
                if asset.metadata.result.match else "unknown"
            )
            rule_name = (
                str(asset.metadata.result.rule)
                if asset.metadata.result.rule else "unknown"
            )
            for schedule_start, schedule_end in self.TIME_RANGES:
                # 日をまたがない時間帯
                if schedule_start < schedule_end:
                    if schedule_start <= file_time < schedule_end:
                        key = (file_date, schedule_start,
                               match_name, rule_name)
                        groups[key].append(asset)
                        break
                # 日をまたぐ時間帯 (23:00-1:00)
                else:
                    if file_time >= schedule_start or file_time < schedule_end:
                        adjusted_date = (
                            file_date
                            if file_time >= schedule_start
                            else file_date - dtmod.timedelta(days=1)
                        )
                        key = (adjusted_date, schedule_start,
                               match_name, rule_name)
                        groups[key].append(asset)
                        break
        return groups

    def execute(self) -> list[Path]:
        """録画フォルダ内の動画を編集して返す。"""
        assets = self._collect_assets()
        groups = self._group_assets(assets)
        edited: list[Path] = []
        for key, clips in groups.items():
            if not clips:
                continue
            target_asset = clips[0]
            if len(clips) > 1:
                merged_path = self.ffmpeg.merge([c.video for c in clips])
                target_asset = VideoAsset.load(merged_path)
                target_asset.metadata = clips[0].metadata
                self.logger.info(
                    "結合完了",
                    group=str(key),
                    clips=[c.video.name for c in clips],
                )
            out = self.editor.process(target_asset.video)
            if target_asset.subtitle:
                self.ffmpeg.embed_subtitle(out, target_asset.subtitle)
            target = self.repo.save_edited(Path(out))
            edited.append(target)
        return edited
