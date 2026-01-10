"""録画済み動画の自動編集サービス。

Phase 9 リファクタリング:
- VideoGroupingService: グループ化ロジックを分離
- TitleDescriptionGenerator: タイトル・説明生成を分離
- ThumbnailGenerator: サムネイル生成を分離
- SubtitleProcessor: 字幕処理・音声読み上げを分離

AutoEditor は全体のオーケストレーション（実行制御）のみを担当。
"""

from __future__ import annotations

import asyncio
import datetime
from pathlib import Path
from typing import List

from splat_replay.application.interfaces import (
    ConfigPort,
    FileSystemPort,
    ImageSelector,
    LoggerPort,
    PathsPort,
    SubtitleEditorPort,
    TextToSpeechPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.application.services.common.progress import ProgressReporter
from splat_replay.domain.models import VideoAsset

from .editing_state import EditingState
from .subtitle_processor import SubtitleProcessor
from .thumbnail_generator import ThumbnailGenerator
from .title_description_generator import TitleDescriptionGenerator
from .video_grouping_service import VideoGroupingService


class AutoEditor:
    """録画済み動画の編集を行うサービス（オーケストレーター）。"""

    def __init__(
        self,
        logger: LoggerPort,
        config: ConfigPort,
        paths: PathsPort,
        video_editor: VideoEditorPort,
        subtitle_editor: SubtitleEditorPort,
        image_selector: ImageSelector,
        text_to_speech: TextToSpeechPort,
        repo: VideoAssetRepositoryPort,
        file_system: FileSystemPort,
        progress: ProgressReporter,
    ):
        self.repo = repo
        self.logger = logger
        self.config = config
        self.settings = config.get_video_edit_settings()
        self.video_editor = video_editor
        self.progress = progress
        self._file_system = file_system
        self._cancelled: bool = False

        # Phase 9: 責務を分離したサービスを組み立てる
        self.grouping = VideoGroupingService(logger)
        self.title_generator = TitleDescriptionGenerator(
            logger, config, video_editor
        )
        self.thumbnail_generator = ThumbnailGenerator(
            logger, paths, image_selector, file_system
        )
        self.subtitle_processor = SubtitleProcessor(
            logger,
            config,
            subtitle_editor,
            text_to_speech,
            video_editor,
            repo,
            file_system,
        )
        self._state = EditingState()

    def request_cancel(self) -> None:
        """Request cancellation; takes effect between groups/steps."""
        self._cancelled = True

    def get_status(self) -> dict[str, object]:
        """現在の編集状態を取得する。

        Returns:
            状態辞書ー
            - phase: str - 処理フェーズ（idle/running/succeeded/failed/cancelled）
            - is_running: bool - 実行中かどうか
            - message: str - 状態メッセージ
            - progress: int - 進捗率（0-100）
            - current_item: str - 現在処理中のアイテム
        """
        return {
            "phase": self._state.phase,
            "is_running": self._state.is_running,
            "message": self._state.message,
            "progress": self._state.progress,
            "current_item": self._state.current_item,
        }

    async def execute(self) -> list[Path]:
        """編集を実行し、編集済み動画のパスリストを返す。"""
        self.settings = self.config.get_video_edit_settings()
        self.logger.info("自動編集を開始します")
        self._state = self._state.with_running("編集処理を開始しています", 0)
        edited: list[Path] = []

        assets = self.repo.list_recordings()
        groups = self.grouping.group_by_timeslot(assets)

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

        total_groups = len([g for g in groups.values() if g])
        completed_groups = 0

        for idx, (key, group) in enumerate(groups.items()):
            if self._cancelled:
                self.progress.finish(
                    task_id, False, "自動編集をキャンセルしました"
                )
                self.logger.info("自動編集をキャンセルしました")
                self._state = self._state.with_cancelled()
                return edited
            if not group:
                continue
            day, time_slot, match_name, rule_name = key
            label = f"{day.strftime('%m/%d')} {time_slot.strftime('%H')}時～ {match_name} {rule_name}"

            # 進捗率を更新
            progress_percent = (
                int((completed_groups / total_groups) * 100)
                if total_groups > 0
                else 0
            )
            self._state = self._state.with_progress(progress_percent, label)

            # 現在処理中のアイテムを明示 (GUI のタスクリスト更新用)
            self.progress.item_stage(
                task_id,
                idx,
                "edit_group",
                "グループ編集",
                message=label,
            )

            try:
                target = await self._edit(
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
                completed_groups += 1
                edited.append(target)
            except Exception as e:
                self.logger.error(
                    "Video edit failed",
                    group_label=label,
                    error=str(e),
                )
                # 失敗したグループをスキップして次へ
                self.progress.advance(task_id)
                continue

        if self._cancelled:
            self.progress.finish(
                task_id, False, "自動編集をキャンセルしました"
            )
            self.logger.info("自動編集をキャンセルしました")
            self._state = self._state.with_cancelled()
        else:
            self.progress.finish(task_id, True, "自動編集を完了しました")
            self._state = self._state.with_succeeded("編集完了")
        self.logger.info("自動編集を完了しました", edited=edited)
        return edited

    async def _edit(
        self,
        idx: int,
        day: datetime.date,
        time_slot: datetime.time,
        match_name: str,
        rule_name: str,
        group: List[VideoAsset],
    ) -> Path:
        """1つのグループを編集する。"""
        target = self._make_filename(
            group, day, time_slot, match_name, rule_name
        )
        task_id = "auto_edit"

        # 動画結合
        self.progress.item_stage(
            task_id,
            idx,
            "concat",
            "動画結合",
            message=f"{len(group)}本の動画を結合",
        )
        await self._merge_videos(target, group)

        # 字幕編集
        self.progress.item_stage(
            task_id,
            idx,
            "subtitle",
            "字幕編集",
        )
        await self.subtitle_processor.create_and_embed(target, group)

        # メタデータ編集
        self.progress.item_stage(
            task_id,
            idx,
            "metadata",
            "メタデータ編集",
        )
        await self._save_metadata(target, group, day, time_slot)

        # サムネイル編集
        self.progress.item_stage(
            task_id,
            idx,
            "thumbnail",
            "サムネイル編集",
        )
        await self._save_thumbnail(target, group)

        # 音量調整
        if self.settings.volume_multiplier != 1.0:
            self.progress.item_stage(
                task_id,
                idx,
                "volume",
                "音量調整",
                message=f"x{self.settings.volume_multiplier}",
            )
            await self._change_volume(target, self.settings.volume_multiplier)

        return target

    def _make_filename(
        self,
        group: List[VideoAsset],
        day: datetime.date,
        time_slot: datetime.time,
        match_name: str,
        rule_name: str,
    ) -> Path:
        """編集後のファイル名を生成する。"""
        ext = group[0].video.suffix
        filename = f"{day.strftime('%Y%m%d')}_{time_slot.strftime('%H')}_{match_name}_{rule_name}{ext}"
        target = group[0].video.with_name(filename)
        return target

    async def _merge_videos(
        self, target: Path, group: List[VideoAsset]
    ) -> None:
        """動画を結合する。

        破損した動画ファイルは自動的にスキップされる。
        """
        # 有効な動画ファイルのみをフィルタリング
        valid_videos = []
        for asset in group:
            length = await self.video_editor.get_video_length(asset.video)
            if length is None or length <= 0:
                self.logger.warning(
                    "Invalid video file skipped during merge",
                    video=str(asset.video),
                )
                continue
            valid_videos.append(asset.video)

        if not valid_videos:
            raise ValueError("No valid video files to merge")

        if len(valid_videos) > 1:
            await self.video_editor.merge(valid_videos, target)
            return

        # 単一ファイルの場合はコピー
        data = await asyncio.to_thread(
            self._file_system.read_bytes, valid_videos[0]
        )
        await asyncio.to_thread(self._file_system.write_bytes, target, data)

    async def _save_metadata(
        self,
        target: Path,
        group: List[VideoAsset],
        day: datetime.date,
        time_slot: datetime.time,
    ) -> None:
        """メタデータをJSONファイルとして保存する。"""
        title, description = await self.title_generator.generate(
            group,
            day,
            time_slot,
        )
        self.logger.info("タイトル編集", title=title)
        self.logger.debug("説明編集", description=description)

        metadata = {
            "title": title,
            "description": description,
        }

        await self.video_editor.embed_metadata(target, metadata)

        # メタデータをリポジトリ経由で保存
        await asyncio.to_thread(
            self.repo.save_edited_metadata_dict, target, metadata
        )

    async def _save_thumbnail(
        self, target: Path, group: List[VideoAsset]
    ) -> None:
        """サムネイルを作成して動画とリポジトリに保存する。"""
        thumb = await asyncio.to_thread(self.thumbnail_generator.create, group)
        if not thumb or not self._file_system.is_file(thumb):
            self.logger.warning("Thumbnail generation failed")
            return

        try:
            # サムネイルをリポジトリ経由で保存
            thumb_data = await asyncio.to_thread(
                self._file_system.read_bytes, thumb
            )
            await self.video_editor.embed_thumbnail(target, thumb_data)
            await asyncio.to_thread(
                self.repo.save_edited_thumbnail, target, thumb_data
            )
        finally:
            # 一時ファイルを削除
            await asyncio.to_thread(
                self._file_system.unlink, thumb, missing_ok=True
            )

    async def _change_volume(self, target: Path, multiplier: float) -> None:
        """動画の音量を調整する。"""
        if multiplier == 1.0:
            return
        await self.video_editor.change_volume(target, multiplier)
