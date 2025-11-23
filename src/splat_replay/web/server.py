"""FastAPI web server for Splat Replay.

Pull 型フレーム取得 (long-poll) と MJPEG ストリームを提供する。
従来の WebSocket フレーム配信は廃止。
"""

from __future__ import annotations

import asyncio
import datetime
import time
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
    cast,
)

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from sse_starlette.sse import EventSourceResponse
from structlog.stdlib import BoundLogger

from splat_replay.application.events.types import EventTypes
from splat_replay.application.interfaces import CommandDispatcher
from splat_replay.application.services import (
    AutoRecorder,
    DeviceChecker,
    ErrorHandler,
    RecordingPreparationService,
    SystemCheckService,
    SystemSetupService,
)
from splat_replay.application.services.installer_service import (
    InstallerService,
)
from splat_replay.application.services.settings_service import (
    FieldValue,
    SectionUpdate,
    SettingsService,
    SettingsServiceError,
    UnknownSettingsFieldError,
    UnknownSettingsSectionError,
)
from splat_replay.web.installer_router import create_installer_router
from splat_replay.application.use_cases import UploadUseCase
from splat_replay.domain.models import (
    BattleResult,
    SalmonResult,
    VideoAsset,
)
from splat_replay.domain.models.rate import RateBase
from splat_replay.infrastructure.runtime.events import EventBus
from splat_replay.shared.paths import PROJECT_ROOT, RUNTIME_ROOT


class SettingsUpdateSection(BaseModel):
    id: str
    values: Dict[str, Any]


class SettingsUpdateRequest(BaseModel):
    sections: List[SettingsUpdateSection]


class MetadataUpdateRequest(BaseModel):
    """録画済みビデオのメタデータ更新リクエスト"""

    match: Optional[str] = None
    rule: Optional[str] = None
    stage: Optional[str] = None
    rate: Optional[str] = None
    judgement: Optional[str] = None
    kill: Optional[int] = None
    death: Optional[int] = None
    special: Optional[int] = None


class SubtitleBlock(BaseModel):
    """字幕ブロック"""

    index: int
    start_time: float  # 秒単位
    end_time: float  # 秒単位
    text: str


class SubtitleData(BaseModel):
    """字幕データ"""

    blocks: List[SubtitleBlock]
    video_duration: Optional[float] = None


EditUploadState = Literal["idle", "running", "succeeded", "failed"]
T = TypeVar("T")


class RecordedVideoItem(BaseModel):
    id: str
    path: str
    filename: str
    started_at: Optional[str] = None
    game_mode: Optional[str] = None
    match: Optional[str] = None
    rule: Optional[str] = None
    stage: Optional[str] = None
    rate: Optional[str] = None
    judgement: Optional[str] = None
    kill: Optional[int] = None
    death: Optional[int] = None
    special: Optional[int] = None
    hazard: Optional[int] = None
    golden_egg: Optional[int] = None
    power_egg: Optional[int] = None
    rescue: Optional[int] = None
    rescued: Optional[int] = None
    has_subtitle: bool
    has_thumbnail: bool
    duration_seconds: Optional[float] = None
    size_bytes: Optional[int] = None


class EditedVideoItem(BaseModel):
    id: str
    path: str
    filename: str
    duration_seconds: Optional[float] = None
    has_subtitle: bool
    has_thumbnail: bool
    metadata: Optional[Dict[str, Optional[str]]] = None
    updated_at: Optional[str] = None
    size_bytes: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None


class EditUploadStatus(BaseModel):
    state: EditUploadState
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


class EditUploadTriggerResponse(BaseModel):
    accepted: bool
    status: EditUploadStatus
    message: Optional[str] = None


class WebServer:
    def __init__(
        self,
        device_checker: DeviceChecker,
        recording_preparation_service: RecordingPreparationService,
        auto_recorder: AutoRecorder,
        command_dispatcher: CommandDispatcher,
        logger: BoundLogger,
        settings_service: SettingsService,
        event_bus: EventBus,
        upload_use_case: UploadUseCase,
        installer_service: InstallerService,
        system_check_service: SystemCheckService,
        system_setup_service: SystemSetupService,
        error_handler: ErrorHandler,
    ) -> None:
        self.device_checker = device_checker
        self.recording_preparation_service = recording_preparation_service
        self.auto_recorder = auto_recorder
        self.command_dispatcher = command_dispatcher
        self.logger = logger
        self.settings_service = settings_service
        self.event_bus = event_bus
        self.upload_use_case = upload_use_case
        self.installer_service = installer_service
        self.system_check_service = system_check_service
        self.system_setup_service = system_setup_service
        self.error_handler = error_handler
        self.app = create_app(self)
        self._edit_upload_task: Optional[asyncio.Task[None]] = None
        self._edit_upload_state: EditUploadState = "idle"
        self._edit_upload_last_error: Optional[str] = None
        self._edit_upload_started_at: Optional[float] = None
        self._edit_upload_finished_at: Optional[float] = None

    async def get_device_status(self) -> bool:
        """Check if capture device is connected."""
        try:
            connected = await self.device_checker.wait_for_device_connection(
                timeout=60.0
            )
            return connected
        except Exception as e:
            self.logger.error("デバイス状態チェックエラー", error=str(e))
            return False

    @staticmethod
    def _format_timestamp(ts: Optional[float]) -> Optional[str]:
        if ts is None:
            return None
        return datetime.datetime.fromtimestamp(
            ts, tz=datetime.timezone.utc
        ).isoformat()

    def _current_edit_upload_status(self) -> EditUploadStatus:
        return EditUploadStatus(
            state=self._edit_upload_state,
            started_at=self._format_timestamp(self._edit_upload_started_at),
            finished_at=self._format_timestamp(self._edit_upload_finished_at),
            error=self._edit_upload_last_error,
        )

    async def _dispatch_command(self, name: str, **payload: Any) -> Any:
        future = self.command_dispatcher.submit(name, **payload)
        try:
            loop = asyncio.get_running_loop()
            result = await asyncio.wrap_future(future, loop=loop)
        except RuntimeError:
            result = await asyncio.wrap_future(future)
        except Exception as exc:
            self.logger.error(
                "Command dispatch failed",
                command=name,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to execute command: {name}",
            ) from exc
        if not result.ok:
            detail = str(result.error) if result.error else "unknown error"
            self.logger.error(
                "Command execution error", command=name, error=detail
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail,
            )
        return cast(Any, result.value)

    async def list_recorded_assets(self) -> List[RecordedVideoItem]:
        raw_assets: List[
            Tuple[VideoAsset, float | None]
        ] = await self._dispatch_command("asset.list_with_length")
        items: List[RecordedVideoItem] = []
        for asset, duration in raw_assets:
            metadata = asset.metadata
            started_at: Optional[str] = None
            game_mode: Optional[str] = None
            match_name: Optional[str] = None
            rule_name: Optional[str] = None
            stage_name: Optional[str] = None
            rate_value: Optional[str] = None
            judgement_value: Optional[str] = None
            kill_value: Optional[int] = None
            death_value: Optional[int] = None
            special_value: Optional[int] = None
            hazard: Optional[int] = None
            golden_egg: Optional[int] = None
            power_egg: Optional[int] = None
            rescue: Optional[int] = None
            rescued: Optional[int] = None

            if metadata is not None:
                if metadata.started_at is not None:
                    started_at = metadata.started_at.isoformat()
                game_mode = metadata.game_mode.value
                if metadata.rate is not None:
                    rate_value = str(metadata.rate)
                if metadata.judgement is not None:
                    judgement_value = metadata.judgement.value
                if isinstance(metadata.result, BattleResult):
                    match_name = metadata.result.match.value
                    rule_name = metadata.result.rule.value
                    stage_name = metadata.result.stage.value
                    kill_value = metadata.result.kill
                    death_value = metadata.result.death
                    special_value = metadata.result.special
                elif isinstance(metadata.result, SalmonResult):
                    stage_name = metadata.result.stage.value
                    hazard = metadata.result.hazard
                    golden_egg = metadata.result.golden_egg
                    power_egg = metadata.result.power_egg
                    rescue = metadata.result.rescue
                    rescued = metadata.result.rescued

            subtitle_path = (
                asset.subtitle
                if asset.subtitle is not None
                else asset.video.with_suffix(".srt")
            )
            thumbnail_path = (
                asset.thumbnail
                if asset.thumbnail is not None
                else asset.video.with_suffix(".png")
            )
            has_subtitle = subtitle_path.exists()
            has_thumbnail = thumbnail_path.exists()

            size_bytes: Optional[int] = None
            try:
                size_bytes = asset.video.stat().st_size
            except FileNotFoundError:
                pass

            items.append(
                RecordedVideoItem(
                    id=str(asset.video),
                    path=str(asset.video),
                    filename=asset.video.name,
                    started_at=started_at,
                    game_mode=game_mode,
                    match=match_name,
                    rule=rule_name,
                    stage=stage_name,
                    rate=rate_value,
                    judgement=judgement_value,
                    kill=kill_value,
                    death=death_value,
                    special=special_value,
                    hazard=hazard,
                    golden_egg=golden_egg,
                    power_egg=power_egg,
                    rescue=rescue,
                    rescued=rescued,
                    has_subtitle=has_subtitle,
                    has_thumbnail=has_thumbnail,
                    duration_seconds=duration,
                    size_bytes=size_bytes,
                )
            )
        return items

    async def list_edited_assets(self) -> List[EditedVideoItem]:
        raw_assets: List[
            Tuple[Path, float | None, Dict[str, Any] | None]
        ] = await self._dispatch_command("asset.list_edited_with_length")
        items: List[EditedVideoItem] = []
        for video_path, duration, metadata in raw_assets:
            subtitle_path = video_path.with_suffix(".srt")
            thumbnail_path = video_path.with_suffix(".png")
            has_subtitle = subtitle_path.exists()
            has_thumbnail = thumbnail_path.exists()
            size_bytes: Optional[int] = None
            updated_at: Optional[str] = None
            try:
                stat_result = video_path.stat()
                size_bytes = stat_result.st_size
                updated_at = self._format_timestamp(stat_result.st_mtime)
            except FileNotFoundError:
                pass
            metadata_payload: Optional[Dict[str, Optional[str]]] = None
            title: Optional[str] = None
            description: Optional[str] = None
            if metadata:
                metadata_payload = {
                    key: str(value) if value is not None else None
                    for key, value in metadata.items()
                }
                # titleとdescriptionを抽出
                title = metadata.get("title")
                description = metadata.get("description")
            items.append(
                EditedVideoItem(
                    id=str(video_path),
                    path=str(video_path),
                    filename=video_path.name,
                    duration_seconds=duration,
                    has_subtitle=has_subtitle,
                    has_thumbnail=has_thumbnail,
                    metadata=metadata_payload,
                    updated_at=updated_at,
                    size_bytes=size_bytes,
                    title=title,
                    description=description,
                )
            )
        return items

    async def start_edit_upload(self) -> EditUploadTriggerResponse:
        if self._edit_upload_task and not self._edit_upload_task.done():
            return EditUploadTriggerResponse(
                accepted=False,
                status=self._current_edit_upload_status(),
                message="edit_upload_running",
            )

        self._edit_upload_state = "running"
        self._edit_upload_last_error = None
        self._edit_upload_started_at = time.time()
        self._edit_upload_finished_at = None
        task = asyncio.create_task(self._run_edit_upload())
        self._edit_upload_task = task
        task.add_done_callback(self._on_edit_upload_done)
        return EditUploadTriggerResponse(
            accepted=True, status=self._current_edit_upload_status()
        )

    def get_edit_upload_status(self) -> EditUploadStatus:
        return self._current_edit_upload_status()

    async def update_recorded_metadata(
        self, video_id: str, metadata_update: MetadataUpdateRequest
    ) -> RecordedVideoItem:
        """録画済みビデオのメタデータを更新する。"""
        from splat_replay.domain.models import (
            BattleResult,
            Judgement,
            Match,
            RecordingMetadata,
            Rule,
            Stage,
        )

        # video_id はパスとして扱う。サイドカーファイル(.json)経由の指定にも対応。
        input_path = Path(video_id)
        # 相対パスの場合はランタイムルートからの相対として解決
        if not input_path.is_absolute():
            input_path = RUNTIME_ROOT / video_id

        suffix = input_path.suffix.lower()
        base_path = input_path.with_suffix("")
        metadata_path = (
            input_path if suffix == ".json" else base_path.with_suffix(".json")
        )

        if not metadata_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata file not found: {metadata_path}",
            )

        video_path = (
            input_path
            if suffix in {".mkv", ".mp4"}
            else base_path.with_suffix(".mkv")
        )

        if not video_path.exists():
            for candidate_suffix in (".mkv", ".mp4"):
                candidate = base_path.with_suffix(candidate_suffix)
                if candidate.exists():
                    video_path = candidate
                    break

        # 既存のアセットを取得
        asset: VideoAsset | None = await self._dispatch_command(
            "asset.get", video=video_path
        )
        if asset is None or asset.metadata is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata not found for: {metadata_path}",
            )

        original_metadata: RecordingMetadata = asset.metadata

        # BattleResult のみ更新対象
        if not isinstance(original_metadata.result, BattleResult):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only battle metadata can be updated",
            )

        # メタデータを更新
        updated_result = BattleResult(
            match=Match(metadata_update.match)
            if metadata_update.match
            else original_metadata.result.match,
            rule=Rule(metadata_update.rule)
            if metadata_update.rule
            else original_metadata.result.rule,
            stage=Stage(metadata_update.stage)
            if metadata_update.stage
            else original_metadata.result.stage,
            kill=metadata_update.kill
            if metadata_update.kill is not None
            else original_metadata.result.kill,
            death=metadata_update.death
            if metadata_update.death is not None
            else original_metadata.result.death,
            special=metadata_update.special
            if metadata_update.special is not None
            else original_metadata.result.special,
        )

        # rate の変換処理
        new_rate: RateBase | None = original_metadata.rate
        if metadata_update.rate is not None:
            try:
                new_rate = RateBase.create(metadata_update.rate)
            except (ValueError, TypeError):
                # "未検出" などの文字列の場合は None とする
                new_rate = None

        updated_metadata = RecordingMetadata(
            started_at=original_metadata.started_at,
            game_mode=original_metadata.game_mode,
            rate=new_rate,
            judgement=Judgement(metadata_update.judgement)
            if metadata_update.judgement
            else original_metadata.judgement,
            result=updated_result,
        )

        # メタデータを保存
        await self._dispatch_command(
            "asset.save_edited_metadata",
            video=video_path,
            metadata=updated_metadata,
        )

        # 更新後のアセット情報を返す
        updated_asset: VideoAsset | None = await self._dispatch_command(
            "asset.get", video=video_path
        )
        if updated_asset is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve updated asset: {video_id}",
            )

        duration: float | None = None
        try:
            import cv2 as cv

            cap = cv.VideoCapture(str(video_path))
            if cap.isOpened():
                fps = cap.get(cv.CAP_PROP_FPS)
                frame_count = cap.get(cv.CAP_PROP_FRAME_COUNT)
                if fps > 0:
                    duration = frame_count / fps
                cap.release()
        except Exception:
            pass

        metadata: RecordingMetadata | None = updated_asset.metadata
        started_at: Optional[str] = None
        game_mode: Optional[str] = None
        match_name: Optional[str] = None
        rule_name: Optional[str] = None
        stage_name: Optional[str] = None
        rate_value: Optional[str] = None
        judgement_value: Optional[str] = None
        kill_value: Optional[int] = None
        death_value: Optional[int] = None
        special_value: Optional[int] = None

        if metadata is not None:
            if metadata.started_at is not None:
                started_at = metadata.started_at.isoformat()
            game_mode = metadata.game_mode.value
            if metadata.rate is not None:
                rate_value = str(metadata.rate)
            if metadata.judgement is not None:
                judgement_value = metadata.judgement.value
            if isinstance(metadata.result, BattleResult):
                match_name = metadata.result.match.value
                rule_name = metadata.result.rule.value
                stage_name = metadata.result.stage.value
                kill_value = metadata.result.kill
                death_value = metadata.result.death
                special_value = metadata.result.special

        subtitle_path = (
            updated_asset.subtitle
            if updated_asset.subtitle is not None
            else updated_asset.video.with_suffix(".srt")
        )
        thumbnail_path = (
            updated_asset.thumbnail
            if updated_asset.thumbnail is not None
            else updated_asset.video.with_suffix(".png")
        )
        has_subtitle = subtitle_path.exists()
        has_thumbnail = thumbnail_path.exists()

        size_bytes: Optional[int] = None
        try:
            size_bytes = updated_asset.video.stat().st_size
        except FileNotFoundError:
            pass

        return RecordedVideoItem(
            id=str(updated_asset.video),
            path=str(updated_asset.video),
            filename=updated_asset.video.name,
            started_at=started_at,
            game_mode=game_mode,
            match=match_name,
            rule=rule_name,
            stage=stage_name,
            rate=rate_value,
            judgement=judgement_value,
            kill=kill_value,
            death=death_value,
            special=special_value,
            hazard=None,
            golden_egg=None,
            power_egg=None,
            rescue=None,
            rescued=None,
            has_subtitle=has_subtitle,
            has_thumbnail=has_thumbnail,
            duration_seconds=duration,
            size_bytes=size_bytes,
        )

    async def _run_edit_upload(self) -> None:
        try:
            self.logger.info("Auto edit/upload pipeline started")
            await self.upload_use_case.execute()
            self.logger.info("Auto edit/upload pipeline finished")
            self._edit_upload_state = "succeeded"
        except Exception as exc:
            self._edit_upload_state = "failed"
            self._edit_upload_last_error = str(exc)
            self.logger.error(
                "Auto edit/upload pipeline failed", error=str(exc)
            )
        finally:
            self._edit_upload_finished_at = time.time()

    def _on_edit_upload_done(self, task: asyncio.Future[None]) -> None:
        if task.cancelled():
            if self._edit_upload_state == "running":
                self._edit_upload_state = "failed"
                self._edit_upload_last_error = "cancelled"
            self._edit_upload_finished_at = time.time()
            self.logger.warning("Auto edit/upload pipeline cancelled")
        else:
            exc = task.exception()
            if exc is not None:
                self._edit_upload_state = "failed"
                self._edit_upload_last_error = str(exc)
                self._edit_upload_finished_at = time.time()
                self.logger.error(
                    "Auto edit/upload pipeline raised", error=str(exc)
                )
            elif self._edit_upload_finished_at is None:
                self._edit_upload_finished_at = time.time()
        if self._edit_upload_task is task:
            self._edit_upload_task = None

    async def prepare_recording(self) -> bool:
        """Prepare recording (OBS setup, virtual camera start)."""
        try:
            self.logger.info("Preparing OBS and virtual camera")
            await self.recording_preparation_service.prepare_recording()
            return True
        except Exception as exc:
            self.logger.error(
                "OBS virtual camera setup failed", error=str(exc)
            )
            return False

    async def start_recording(self) -> dict[str, Any]:
        """Start auto recording process."""
        self.logger.info("録画開始リクエスト受信")
        try:
            asyncio.create_task(self._run_recording())
            return {"success": True}

        except Exception as e:
            self.logger.error("録画開始エラー", error=str(e))
            return {"success": False, "error": str(e)}

    async def _run_recording(self) -> None:
        """Run recording in background."""
        try:
            self.logger.info("AutoRecorder 実行開始")

            # Execute auto recorder (this will handle the full recording workflow)
            await self.auto_recorder.execute()

        except Exception as e:
            self.logger.error("録画実行エラー", error=str(e))

    async def manual_start_recording(self) -> dict[str, Any]:
        """手動録画開始。"""
        try:
            await self.auto_recorder.start()
            return {"success": True}
        except Exception as e:
            self.logger.error("手動録画開始エラー", error=str(e))
            return {"success": False, "error": str(e)}

    async def manual_pause_recording(self) -> dict[str, Any]:
        """手動録画一時停止。"""
        try:
            await self.auto_recorder.pause()
            return {"success": True}
        except Exception as e:
            self.logger.error("手動録画一時停止エラー", error=str(e))
            return {"success": False, "error": str(e)}

    async def manual_resume_recording(self) -> dict[str, Any]:
        """手動録画再開。"""
        try:
            await self.auto_recorder.resume()
            return {"success": True}
        except Exception as e:
            self.logger.error("手動録画再開エラー", error=str(e))
            return {"success": False, "error": str(e)}

    async def manual_stop_recording(self) -> dict[str, Any]:
        """手動録画停止。"""
        try:
            await self.auto_recorder.stop()
            return {"success": True}
        except Exception as e:
            self.logger.error("手動録画停止エラー", error=str(e))
            return {"success": False, "error": str(e)}

    def get_recorder_state(self) -> dict[str, str]:
        """録画状態を取得。"""
        from splat_replay.domain.services import RecordState

        state_map = {
            RecordState.STOPPED: "STOPPED",
            RecordState.RECORDING: "RECORDING",
            RecordState.PAUSED: "PAUSED",
        }
        current_state = self.auto_recorder.sm.state
        return {"state": state_map.get(current_state, "UNKNOWN")}

    async def get_recorded_subtitle(self, video_id: str) -> SubtitleData:
        """録画済みビデオの字幕を取得する。"""
        import srt

        input_path = Path(video_id)
        # 相対パスの場合はランタイムルートからの相対として解決
        if not input_path.is_absolute():
            input_path = RUNTIME_ROOT / video_id

        suffix = input_path.suffix.lower()
        base_path = input_path.with_suffix("")
        srt_path = (
            input_path if suffix == ".srt" else base_path.with_suffix(".srt")
        )
        video_path = (
            input_path
            if suffix in {".mkv", ".mp4"}
            else base_path.with_suffix(".mkv")
        )
        if not video_path.exists():
            for candidate_suffix in (".mkv", ".mp4"):
                candidate = base_path.with_suffix(candidate_suffix)
                if candidate.exists():
                    video_path = candidate
                    break

        if not srt_path.exists() and not video_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Neither subtitle nor video file found for: {base_path}",
            )
        blocks: List[SubtitleBlock] = []

        if srt_path.exists():
            try:
                srt_content = srt_path.read_text(encoding="utf-8")
                subtitles = list(srt.parse(srt_content))

                for idx, sub in enumerate(subtitles, start=1):
                    blocks.append(
                        SubtitleBlock(
                            index=idx,
                            start_time=sub.start.total_seconds(),
                            end_time=sub.end.total_seconds(),
                            text=sub.content,
                        )
                    )
            except Exception as exc:
                self.logger.error(
                    "字幕ファイルの読み込みに失敗しました",
                    video_id=video_id,
                    error=str(exc),
                )

        # 動画の長さを取得
        video_duration: Optional[float] = None
        if video_path.exists():
            try:
                import cv2

                cap = cv2.VideoCapture(str(video_path))
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    if fps > 0:
                        video_duration = frame_count / fps
                    cap.release()
            except Exception as exc:
                self.logger.warning(
                    "動画の長さ取得に失敗しました",
                    video_id=video_id,
                    error=str(exc),
                )

        return SubtitleData(blocks=blocks, video_duration=video_duration)

    async def update_recorded_subtitle(
        self, video_id: str, data: SubtitleData
    ) -> SubtitleData:
        """録画済みビデオの字幕を更新する。"""
        import datetime

        import srt

        input_path = Path(video_id)
        # 相対パスの場合はランタイムルートからの相対として解決
        if not input_path.is_absolute():
            input_path = RUNTIME_ROOT / video_id

        suffix = input_path.suffix.lower()
        base_path = input_path.with_suffix("")
        srt_path = (
            input_path if suffix == ".srt" else base_path.with_suffix(".srt")
        )
        video_path = (
            input_path
            if suffix in {".mkv", ".mp4"}
            else base_path.with_suffix(".mkv")
        )
        if not video_path.exists():
            for candidate_suffix in (".mkv", ".mp4"):
                candidate = base_path.with_suffix(candidate_suffix)
                if candidate.exists():
                    video_path = candidate
                    break

        srt_path.parent.mkdir(parents=True, exist_ok=True)

        # 字幕ブロックをSRT形式に変換
        subtitles: List[srt.Subtitle] = []
        for block in sorted(data.blocks, key=lambda b: b.start_time):
            subtitles.append(
                srt.Subtitle(
                    index=block.index,
                    start=datetime.timedelta(seconds=block.start_time),
                    end=datetime.timedelta(seconds=block.end_time),
                    content=block.text,
                )
            )

        # SRTファイルに書き込み
        try:
            srt_content = srt.compose(subtitles)
            srt_path.write_text(srt_content, encoding="utf-8")
            self.logger.info(
                "字幕ファイルを保存しました",
                video_id=video_id,
                srt_path=str(srt_path),
            )

            # イベントを発行
            from splat_replay.infrastructure.runtime.events import Event

            self.event_bus.publish(
                Event(
                    type=EventTypes.ASSET_RECORDED_SUBTITLE_UPDATED,
                    payload={"video_id": video_id, "srt_path": str(srt_path)},
                )
            )

        except Exception as exc:
            self.logger.error(
                "字幕ファイルの保存に失敗しました",
                video_id=video_id,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save subtitle: {exc}",
            ) from exc

        return await self.get_recorded_subtitle(str(srt_path))

    async def delete_recorded_video(self, video_id: str) -> None:
        """録画済みビデオとその関連ファイルを削除する。"""
        video_path = Path(video_id)
        # 相対パスの場合はランタイムルートからの相対として解決
        if not video_path.is_absolute():
            video_path = RUNTIME_ROOT / video_id

        if not video_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}",
            )

        try:
            # 関連ファイルのパスを取得
            base_name = video_path.stem
            video_dir = video_path.parent

            # 削除対象のファイルリスト
            files_to_delete = [video_path]

            # メタデータファイル
            meta_path = video_dir / f"{base_name}.yaml"
            if meta_path.exists():
                files_to_delete.append(meta_path)

            # 字幕ファイル
            srt_path = video_dir / f"{base_name}.srt"
            if srt_path.exists():
                files_to_delete.append(srt_path)

            # サムネイルファイル
            thumbnail_dir = video_dir.parent.parent / "assets" / "thumbnail"
            thumbnail_path = thumbnail_dir / f"{base_name}.png"
            if thumbnail_path.exists():
                files_to_delete.append(thumbnail_path)

            # ファイルを削除
            for file_path in files_to_delete:
                file_path.unlink()
                self.logger.info(f"削除しました: {file_path}")

            # イベントを発行
            from splat_replay.infrastructure.runtime.events import Event

            self.event_bus.publish(
                Event(
                    type=EventTypes.ASSET_RECORDED_DELETED,
                    payload={"video_id": video_id},
                )
            )

            self.logger.info("録画済みビデオを削除しました", video_id=video_id)

        except Exception as exc:
            self.logger.error(
                "録画済みビデオの削除に失敗しました",
                video_id=video_id,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete video: {exc}",
            ) from exc

    async def delete_edited_video(self, video_id: str) -> None:
        """編集済みビデオとその関連ファイルを削除する。"""
        video_path = Path(video_id)
        # 相対パスの場合はランタイムルートからの相対として解決
        if not video_path.is_absolute():
            video_path = RUNTIME_ROOT / video_id

        if not video_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}",
            )

        try:
            # 関連ファイルのパスを取得
            base_name = video_path.stem
            video_dir = video_path.parent

            # 削除対象のファイルリスト
            files_to_delete = [video_path]

            # メタデータファイル
            meta_path = video_dir / f"{base_name}.yaml"
            if meta_path.exists():
                files_to_delete.append(meta_path)

            # 字幕ファイル
            srt_path = video_dir / f"{base_name}.srt"
            if srt_path.exists():
                files_to_delete.append(srt_path)

            # サムネイルファイル
            thumbnail_dir = video_dir.parent.parent / "assets" / "thumbnail"
            thumbnail_path = thumbnail_dir / f"{base_name}.png"
            if thumbnail_path.exists():
                files_to_delete.append(thumbnail_path)

            # ファイルを削除
            for file_path in files_to_delete:
                file_path.unlink()
                self.logger.info(f"削除しました: {file_path}")

            # イベントを発行
            from splat_replay.infrastructure.runtime.events import Event

            self.event_bus.publish(
                Event(
                    type=EventTypes.ASSET_EDITED_DELETED,
                    payload={"video_id": video_id},
                )
            )

            self.logger.info("編集済みビデオを削除しました", video_id=video_id)

        except Exception as exc:
            self.logger.error(
                "編集済みビデオの削除に失敗しました",
                video_id=video_id,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete video: {exc}",
            ) from exc


def create_app(server: WebServer) -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(title="Splat Replay Web API")

    # CORS設定 (開発時)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 静的ファイル配信 (フロントエンド)
    frontend_dist = PROJECT_ROOT / "frontend" / "dist"
    frontend_exists = frontend_dist.exists()

    if frontend_exists:
        # 静的ファイルをマウント (APIルート以外)
        app.mount(
            "/assets",
            StaticFiles(directory=str(frontend_dist / "assets")),
            name="assets",
        )

    # ヘルスチェックエンドポイント (常に有効)
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """ヘルスチェックエンドポイント"""
        return {"status": "ok"}

    # インストーラールーターを登録
    installer_router = create_installer_router(
        installer_service=server.installer_service,
        system_check_service=server.system_check_service,
        system_setup_service=server.system_setup_service,
        error_handler=server.error_handler,
        logger=server.logger,
    )
    app.include_router(installer_router)

    @app.get("/api/settings")
    async def get_settings() -> JSONResponse:
        sections = server.settings_service.fetch_sections()
        return JSONResponse(content={"sections": sections})

    @app.put("/api/settings")
    async def update_settings(
        request: SettingsUpdateRequest,
    ) -> JSONResponse:
        updates: List[SectionUpdate] = [
            {
                "id": section.id,
                "values": cast(Dict[str, FieldValue], section.values),
            }
            for section in request.sections
        ]
        try:
            server.settings_service.update_sections(updates)
        except UnknownSettingsSectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except UnknownSettingsFieldError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            ) from exc
        except SettingsServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        return JSONResponse(content={"status": "ok"})

    @app.get("/api/device/status")
    async def get_device_status() -> JSONResponse:
        # status = await server.get_device_status()
        status = True
        return JSONResponse(content=status)

    @app.post("/api/recording/prepare")
    async def prepare_recording() -> JSONResponse:
        # result = await server.prepare_recording()
        result = True
        return JSONResponse(content={"success": result})

    @app.post("/api/recording/start")
    async def start_recording() -> JSONResponse:
        result = await server.start_recording()
        return JSONResponse(content=result)

    @app.post("/api/recorder/start")
    async def manual_start_recorder() -> JSONResponse:
        """手動録画開始。"""
        result = await server.manual_start_recording()
        return JSONResponse(content=result)

    @app.post("/api/recorder/pause")
    async def manual_pause_recorder() -> JSONResponse:
        """手動録画一時停止。"""
        result = await server.manual_pause_recording()
        return JSONResponse(content=result)

    @app.post("/api/recorder/resume")
    async def manual_resume_recorder() -> JSONResponse:
        """手動録画再開。"""
        result = await server.manual_resume_recording()
        return JSONResponse(content=result)

    @app.post("/api/recorder/stop")
    async def manual_stop_recorder() -> JSONResponse:
        """手動録画停止。"""
        result = await server.manual_stop_recording()
        return JSONResponse(content=result)

    @app.get("/api/recorder/state")
    async def get_recorder_state() -> JSONResponse:
        """録画状態取得。"""
        result = server.get_recorder_state()
        return JSONResponse(content=result)

    @app.get(
        "/api/assets/recorded",
        response_model=List[RecordedVideoItem],
    )
    async def get_recorded_assets() -> List[RecordedVideoItem]:
        return await server.list_recorded_assets()

    @app.get(
        "/api/assets/edited",
        response_model=List[EditedVideoItem],
    )
    async def get_edited_assets() -> List[EditedVideoItem]:
        return await server.list_edited_assets()

    @app.post(
        "/api/process/edit-upload",
        response_model=EditUploadTriggerResponse,
    )
    async def trigger_edit_upload() -> JSONResponse:
        result = await server.start_edit_upload()
        status_code = (
            status.HTTP_202_ACCEPTED
            if result.accepted
            else status.HTTP_409_CONFLICT
        )
        return JSONResponse(
            status_code=status_code,
            content=result.dict(),
        )

    @app.get(
        "/api/process/status",
        response_model=EditUploadStatus,
    )
    async def get_edit_upload_status() -> EditUploadStatus:
        return server.get_edit_upload_status()

    @app.get("/api/recording/metadata")
    async def get_current_metadata() -> JSONResponse:
        """現在のセッションのメタデータを取得。"""
        try:
            metadata = server.auto_recorder.metadata.to_dict()
            return JSONResponse(content=metadata)
        except Exception as e:
            server.logger.error("メタデータ取得エラー", error=str(e))
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to get metadata"},
            )

    @app.post("/api/recording/metadata")
    async def update_metadata(request: dict[str, object]) -> JSONResponse:
        """手動編集されたメタデータでセッションのメタデータを更新。"""
        try:
            from splat_replay.infrastructure.runtime.events import Event

            server.auto_recorder.metadata.update_from_dict(request)
            # 更新イベントを発行
            server.event_bus.publish(
                Event(
                    type=EventTypes.RECORDER_METADATA_UPDATED,
                    payload={
                        "metadata": server.auto_recorder.metadata.to_dict()
                    },
                )
            )
            return JSONResponse(
                content={
                    "status": "success",
                    "metadata": server.auto_recorder.metadata.to_dict(),
                }
            )
        except Exception as e:
            server.logger.error("メタデータ更新エラー", error=str(e))
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to update metadata"},
            )

    @app.patch(
        "/api/assets/recorded/{video_id:path}/metadata",
        response_model=RecordedVideoItem,
    )
    async def update_recorded_asset_metadata(
        video_id: str, metadata: MetadataUpdateRequest
    ) -> RecordedVideoItem:
        """録画済みビデオのメタデータを更新する。"""
        return await server.update_recorded_metadata(video_id, metadata)

    @app.delete("/api/assets/recorded/{video_id:path}")
    async def delete_recorded_asset(video_id: str) -> JSONResponse:
        """録画済みビデオを削除する。"""
        await server.delete_recorded_video(video_id)
        return JSONResponse(content={"status": "ok"})

    @app.delete("/api/assets/edited/{video_id:path}")
    async def delete_edited_asset(video_id: str) -> JSONResponse:
        """編集済みビデオを削除する。"""
        await server.delete_edited_video(video_id)
        return JSONResponse(content={"status": "ok"})

    @app.get(
        "/api/subtitles/recorded/{video_id:path}",
        response_model=SubtitleData,
    )
    async def get_recorded_subtitle(video_id: str) -> SubtitleData:
        """録画済みビデオの字幕を取得する。"""
        return await server.get_recorded_subtitle(video_id)

    @app.put(
        "/api/subtitles/recorded/{video_id:path}",
        response_model=SubtitleData,
    )
    async def update_recorded_subtitle(
        video_id: str, data: SubtitleData
    ) -> SubtitleData:
        """録画済みビデオの字幕を更新する。"""
        return await server.update_recorded_subtitle(video_id, data)

    @app.get("/api/videos/recorded/{video_id:path}")
    async def get_recorded_video(video_id: str) -> FileResponse:
        """録画済みビデオファイルを取得する。"""
        video_path = Path(video_id)
        # 相対パスの場合はランタイムルートからの相対として解決
        # （PyInstaller環境では実行ファイルのあるディレクトリが基準）
        if not video_path.is_absolute():
            video_path = RUNTIME_ROOT / video_id

        if not video_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}",
            )
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=video_path.name,
        )

    @app.get("/api/thumbnails/recorded/{filename}")
    async def get_recorded_thumbnail(filename: str) -> FileResponse:
        """録画済みビデオのサムネイルを取得する。"""
        # recorded ディレクトリからサムネイルを取得
        recorded_dir: Path = await server._dispatch_command(
            "asset.get_recorded_dir"
        )
        # ファイル名がそのまま使える場合とそうでない場合の両方に対応
        thumbnail_path = recorded_dir / filename
        if not thumbnail_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thumbnail not found: {filename}",
            )
        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/png",
            filename=thumbnail_path.name,
        )

    @app.get("/api/videos/edited/{video_id:path}")
    async def get_edited_video(video_id: str) -> FileResponse:
        """編集済みビデオファイルを取得する。"""
        video_path = Path(video_id)
        # 相対パスの場合はランタイムルートからの相対として解決
        # （PyInstaller環境では実行ファイルのあるディレクトリが基準）
        if not video_path.is_absolute():
            video_path = RUNTIME_ROOT / video_id

        if not video_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found: {video_id}",
            )
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=video_path.name,
        )

    @app.get("/api/thumbnails/edited/{filename}")
    async def get_edited_thumbnail(filename: str) -> FileResponse:
        """編集済みビデオのサムネイルを取得する。"""
        # edited ディレクトリからサムネイルを取得
        edited_dir: Path = await server._dispatch_command(
            "asset.get_edited_dir"
        )
        # ファイル名がそのまま使える場合とそうでない場合の両方に対応
        thumbnail_path = edited_dir / filename
        if not thumbnail_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thumbnail not found: {filename}",
            )
        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/png",
            filename=thumbnail_path.name,
        )

    @app.get("/api/events/recorder-state")
    async def recorder_state_events() -> EventSourceResponse:
        """録画状態イベントをSSE (Server-Sent Events) でストリーム配信。"""
        import json

        async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
            sub = server.event_bus.subscribe(
                event_types=[EventTypes.RECORDER_STATE]
            )
            try:
                while True:
                    events = sub.poll(max_items=10)
                    for ev in events:
                        # ev.payload = {"state": "RECORDING" | "PAUSED" | "STOPPED"}
                        data = {"state": ev.payload.get("state", "UNKNOWN")}
                        yield {
                            "event": "recorder_state",
                            "data": json.dumps(data),
                        }
                    if not events:
                        await asyncio.sleep(0.1)
            finally:
                sub.close()

        return EventSourceResponse(event_generator())

    @app.get("/api/events/metadata")
    async def metadata_events() -> EventSourceResponse:
        """メタデータ更新イベントをSSE (Server-Sent Events) でストリーム配信。"""
        import json

        async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
            sub = server.event_bus.subscribe(
                event_types=[
                    EventTypes.RECORDER_METADATA_UPDATED,
                    EventTypes.RECORDER_RESET,
                ]
            )
            try:
                while True:
                    events = sub.poll(max_items=10)
                    for ev in events:
                        if ev.type == EventTypes.RECORDER_RESET:
                            yield {
                                "event": "recorder_reset",
                                "data": json.dumps({}),
                            }
                        elif ev.type == EventTypes.RECORDER_METADATA_UPDATED:
                            # ev.payload = {"metadata": {...}}
                            metadata = ev.payload.get("metadata", {})
                            yield {
                                "event": "metadata_updated",
                                "data": json.dumps(metadata),
                            }
                    if not events:
                        await asyncio.sleep(0.1)
            finally:
                sub.close()

        return EventSourceResponse(event_generator())

    @app.get("/api/events/assets")
    async def asset_events() -> EventSourceResponse:
        """録画/編集アセット関連イベントを SSE でストリーム配信。"""
        import json

        event_types = [
            EventTypes.ASSET_RECORDED_SAVED,
            EventTypes.ASSET_RECORDED_METADATA_UPDATED,
            EventTypes.ASSET_RECORDED_SUBTITLE_UPDATED,
            EventTypes.ASSET_RECORDED_DELETED,
            EventTypes.ASSET_EDITED_SAVED,
            EventTypes.ASSET_EDITED_DELETED,
        ]

        async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
            sub = server.event_bus.subscribe(event_types=event_types)
            try:
                while True:
                    events = sub.poll(max_items=10)
                    for ev in events:
                        payload = dict(ev.payload)
                        yield {
                            "event": "asset_event",
                            "data": json.dumps(
                                {"type": ev.type, "payload": payload}
                            ),
                        }
                    if not events:
                        await asyncio.sleep(0.1)
            finally:
                sub.close()

        return EventSourceResponse(event_generator())

    @app.get("/api/events/progress")
    async def progress_events() -> EventSourceResponse:
        """進捗イベントをSSE (Server-Sent Events) でストリーム配信。"""
        import json

        async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
            sub = server.event_bus.subscribe(
                event_types=[
                    "progress.start",
                    "progress.total",
                    "progress.stage",
                    "progress.advance",
                    "progress.finish",
                    "progress.items",
                    "progress.item_stage",
                    "progress.item_finish",
                ]
            )
            try:
                while True:
                    events = sub.poll(max_items=10)
                    if events:
                        server.logger.info(
                            "SSE: Polling progress events",
                            count=len(events),
                        )
                    for ev in events:
                        server.logger.info(
                            "SSE: Sending progress event",
                            event_type=ev.type,
                        )
                        yield {
                            "event": "progress_event",
                            "data": json.dumps(ev.payload),
                        }
                    if not events:
                        await asyncio.sleep(0.1)
            finally:
                sub.close()

        return EventSourceResponse(event_generator())

    # === SPA用 Catch-all ルート (最後に定義してAPIルートより優先度を下げる) ===
    if frontend_exists:

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str) -> FileResponse:
            """SPAフロントエンド配信 (APIパス以外)"""
            # APIパスは既に上記で定義済みなので、ここには来ない
            # ただし念のため明示的に除外
            if full_path.startswith("api/"):
                raise HTTPException(
                    status_code=404, detail="API endpoint not found"
                )

            # ファイルが存在する場合はそれを返す
            file_path = frontend_dist / full_path
            if file_path.is_file():
                return FileResponse(file_path)

            # それ以外はindex.htmlを返す (SPAルーティング)
            return FileResponse(frontend_dist / "index.html")

    return app


__all__ = ["WebServer", "create_app"]
