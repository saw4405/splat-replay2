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
import hashlib
import json
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


class EditedCommitCleanupError(RuntimeError):
    """編集成果物確定後の元録画cleanupに失敗した。"""


SOURCE_RECORDINGS_METADATA_KEY = "splat_replay_source_recordings"


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
    ) -> None:
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
        self._cancelled = False
        self.settings = self.config.get_video_edit_settings()
        self.logger.info("自動編集を開始します")
        self._state = self._state.with_running("編集処理を開始しています", 0)
        assets = self.repo.list_recordings()
        edited, recovered_source_names = self._recover_committed_inputs(assets)
        assets = [
            asset
            for asset in assets
            if asset.video.name not in recovered_source_names
        ]
        groups = self.grouping.group_by_timeslot(assets)

        task_id = "auto_edit"
        items: list[str] = []
        clips_payload: list[dict[str, object]] = []
        committed_group_indexes: set[int] = set()

        for idx, (key, group) in enumerate(groups.items()):
            if not group:
                continue
            day, time_slot, match_name, rule_name = key
            label = f"{day.strftime('%m/%d')} {time_slot.strftime('%H')}時～ {match_name} {rule_name}"

            committed_target = (
                self.repo.get_edited_dir()
                / self._make_filename(
                    group, day, time_slot, match_name, rule_name
                ).name
            )
            if committed_target in self.repo.list_edited():
                self.logger.info(
                    "確定済み編集動画を検出したため元録画の削除から再開します",
                    path=str(committed_target),
                )
                for asset in group:
                    if not self.repo.delete_recording(asset.video):
                        raise EditedCommitCleanupError(
                            f"録画済み動画を削除できませんでした: {asset.video}"
                        )
                edited.append(committed_target)
                committed_group_indexes.add(idx)
                continue
            items.append(label)

            group_clips = []
            for asset in group:
                length = await self.video_editor.get_video_length(asset.video)
                duration_seconds = (
                    int(length) if (length is not None and length > 0) else 300
                )

                judgement = (
                    asset.metadata.judgement.value
                    if (asset.metadata and asset.metadata.judgement)
                    else "WIN"
                )

                stage_name = ""
                kill = 0
                death = 0
                special = 0
                gold_medals = 0
                silver_medals = 0
                if asset.metadata and asset.metadata.result:
                    res = asset.metadata.result
                    if hasattr(res, "stage") and res.stage:
                        stage_name = res.stage.value
                    if hasattr(res, "kill"):
                        kill = res.kill
                    if hasattr(res, "death"):
                        death = res.death
                    if hasattr(res, "special"):
                        special = res.special
                    if hasattr(res, "gold_medals"):
                        gold_medals = res.gold_medals
                    if hasattr(res, "silver_medals"):
                        silver_medals = res.silver_medals

                rate_info = None
                if asset.metadata and asset.metadata.rate:
                    rate = asset.metadata.rate
                    rate_info = {"type": rate.label, "value": str(rate)}

                video_id = f"recorded/{asset.video.name}"
                group_clips.append(
                    {
                        "video_id": video_id,
                        "duration_seconds": duration_seconds,
                        "judgement": judgement,
                        "stage_name": stage_name,
                        "kill": kill,
                        "death": death,
                        "special": special,
                        "gold_medals": gold_medals,
                        "silver_medals": silver_medals,
                        "rate": rate_info,
                    }
                )

            clips_payload.append(
                {
                    "group_index": len(items) - 1,
                    "date_label": f"{day.strftime('%m/%d')} {time_slot.strftime('%H:%M')}～",
                    "match_name": match_name,
                    "rule_name": rule_name,
                    "thumbnail_filename": (
                        f"{day.strftime('%Y%m%d')}_{time_slot.strftime('%H')}_"
                        f"{match_name}_{rule_name}.png"
                    ),
                    "video_assets": group_clips,
                }
            )

        self.progress.start_task(
            task_id, "自動編集", len(items), items=items, clips=clips_payload
        )

        total_groups = len(
            [
                group
                for idx, group in enumerate(groups.values())
                if group and idx not in committed_group_indexes
            ]
        )
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
            if idx in committed_group_indexes:
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
                target, metadata = await self._edit(
                    idx, day, time_slot, match_name, rule_name, group
                )
                self.logger.info("動画編集を開始します", path=str(target))
                target = self.repo.save_edited(Path(target))
                for asset in group:
                    self.logger.info(
                        "録画済み動画を削除します", path=str(asset.video)
                    )
                    if not self.repo.delete_recording(asset.video):
                        raise EditedCommitCleanupError(
                            f"録画済み動画を削除できませんでした: {asset.video}"
                        )
                # 保存ステップを通知し、全体の進捗を 1 進める
                self.progress.item_stage(
                    task_id,
                    idx,
                    "save",
                    "録画済動画削除・編集済動画保存",
                    message=metadata.get("title") or target.name,
                )
                self.progress.advance(task_id)
                completed_groups += 1
                edited.append(target)
            except Exception as e:
                self.logger.error(
                    "Video edit failed",
                    group_label=label,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                # 失敗したグループをスキップして次へ
                self.progress.advance(task_id)
                if isinstance(e, EditedCommitCleanupError):
                    self.progress.finish(
                        task_id,
                        False,
                        "編集成果物確定後の元録画削除に失敗しました",
                    )
                    self._state = self._state.with_failed(str(e))
                    raise
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
    ) -> tuple[Path, dict[str, str]]:
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
        await self._merge_videos(idx, target, group)

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
        metadata = await self._prepare_metadata(group, day, time_slot)

        # サムネイル編集
        self.progress.item_stage(
            task_id,
            idx,
            "thumbnail",
            "サムネイル編集",
            message="サムネイル画像を生成中",
        )
        await self._save_thumbnail(target, group, idx, metadata)

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

        return target, metadata

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
        source_identity = "\n".join(self._source_recording_names(group))
        source_id = hashlib.sha256(
            source_identity.encode("utf-8")
        ).hexdigest()[:12]
        filename = (
            f"{day.strftime('%Y%m%d')}_{time_slot.strftime('%H')}_"
            f"{match_name}_{rule_name}_{source_id}{ext}"
        )
        target = group[0].video.with_name(filename)
        return target

    def _recover_committed_inputs(
        self, assets: List[VideoAsset]
    ) -> tuple[list[Path], set[str]]:
        """commit済み成果物のmanifestから未完了cleanupを再開する。"""
        assets_by_name = {asset.video.name: asset for asset in assets}
        recovered: list[Path] = []
        recovered_source_names: set[str] = set()

        for committed in self.repo.list_edited():
            metadata = self.repo.get_edited_metadata(committed) or {}
            source_names = self._parse_source_recording_names(
                metadata.get(SOURCE_RECORDINGS_METADATA_KEY)
            )
            pending_names = [
                name for name in source_names if name in assets_by_name
            ]
            if not pending_names:
                continue

            self.logger.info(
                "編集成果物manifestを検出したため元録画の削除から再開します",
                path=str(committed),
                source_count=len(pending_names),
            )
            for source_name in pending_names:
                source = assets_by_name[source_name].video
                if not self.repo.delete_recording(source):
                    raise EditedCommitCleanupError(
                        f"録画済み動画を削除できませんでした: {source}"
                    )
                recovered_source_names.add(source_name)
            recovered.append(committed)

        return recovered, recovered_source_names

    @staticmethod
    def _source_recording_names(group: List[VideoAsset]) -> list[str]:
        """保存先の移動後も安定する入力録画識別子を返す。"""
        return sorted(asset.video.name for asset in group)

    @staticmethod
    def _parse_source_recording_names(value: str | None) -> list[str]:
        if value is None:
            return []
        try:
            decoded = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(decoded, list) or not all(
            isinstance(item, str) for item in decoded
        ):
            return []
        return decoded

    async def _merge_videos(
        self, idx: int, target: Path, group: List[VideoAsset]
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

            def on_progress(percent: float, message: str | None) -> None:
                self.progress.item_stage(
                    "auto_edit",
                    idx,
                    "concat",
                    "動画結合",
                    message=message or f"{len(valid_videos)}本の動画を結合中",
                    progress_percent=percent,
                )

            await self.video_editor.merge(
                valid_videos, target, on_progress=on_progress
            )
            return

        # 単一ファイルの場合はコピー
        data = await asyncio.to_thread(
            self._file_system.read_bytes, valid_videos[0]
        )
        await asyncio.to_thread(self._file_system.write_bytes, target, data)

    async def _prepare_metadata(
        self,
        group: List[VideoAsset],
        day: datetime.date,
        time_slot: datetime.time,
    ) -> dict[str, str]:
        """動画に埋め込むメタデータを作成する。"""
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
            SOURCE_RECORDINGS_METADATA_KEY: json.dumps(
                self._source_recording_names(group),
                ensure_ascii=False,
            ),
        }

        return metadata

    async def _save_thumbnail(
        self,
        target: Path,
        group: List[VideoAsset],
        idx: int,
        metadata: dict[str, str],
    ) -> None:
        """サムネイルを作成し、メタデータと一緒に動画へ保存する。"""
        thumb = await asyncio.to_thread(self.thumbnail_generator.create, group)
        if not thumb or not self._file_system.is_file(thumb):
            self.logger.warning("Thumbnail generation failed")
            await self.video_editor.embed_metadata(target, metadata)
            await self._save_metadata_sidecar(target, metadata)
            return

        try:
            # サムネイルをリポジトリ経由で保存
            thumb_data = await asyncio.to_thread(
                self._file_system.read_bytes, thumb
            )
            edited_thumbnail_target = self.repo.get_edited_dir() / target.name
            saved_preview_thumbnail = await asyncio.to_thread(
                self.repo.save_edited_thumbnail,
                edited_thumbnail_target,
                thumb_data,
            )
            if saved_preview_thumbnail:
                self.progress.item_stage(
                    "auto_edit",
                    idx,
                    "thumbnail",
                    "サムネイル編集",
                    progress_percent=0.0,
                )

            def on_progress(percent: float, message: str | None) -> None:
                self.progress.item_stage(
                    "auto_edit",
                    idx,
                    "thumbnail",
                    "サムネイル編集",
                    message=message or "メタデータ・サムネイルを埋め込み中",
                    progress_percent=percent,
                )

            await self.video_editor.embed_metadata_and_thumbnail(
                target,
                metadata,
                thumb_data,
                on_progress=on_progress,
            )
            await self._save_metadata_sidecar(target, metadata)
            if not saved_preview_thumbnail:
                await asyncio.to_thread(
                    self.repo.save_edited_thumbnail, target, thumb_data
                )
        finally:
            # 一時ファイルを削除
            await asyncio.to_thread(
                self._file_system.unlink, thumb, missing_ok=True
            )

    async def _save_metadata_sidecar(
        self, target: Path, metadata: dict[str, str]
    ) -> None:
        """メタデータをリポジトリ経由で保存する。"""
        saved = await asyncio.to_thread(
            self.repo.save_edited_metadata_dict, target, metadata
        )
        if not saved:
            raise RuntimeError(
                f"編集済み動画のメタデータを保存できませんでした: {target}"
            )

    async def _change_volume(self, target: Path, multiplier: float) -> None:
        """動画の音量を調整する。"""
        if multiplier == 1.0:
            return
        await self.video_editor.change_volume(target, multiplier)
