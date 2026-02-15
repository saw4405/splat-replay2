"""アセット（録画・編集済み動画）管理ルーター。

責務：
- 録画済み/編集済みビデオの一覧取得
- 録画済み/編集済みビデオの削除
- ビデオファイル・サムネイル画像の配信
- 編集・アップロード処理のトリガー/状態取得
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse

from splat_replay.interface.web.schemas import (
    EditedVideoItem,
    EditUploadStatus,
    EditUploadTriggerResponse,
    RecordedVideoItem,
)

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


def create_assets_router(server: WebAPIServer) -> APIRouter:
    """アセット管理ルーターを作成。

    Args:
        server: WebAPIServerインスタンス

    Returns:
        設定済みのAPIRouter
    """
    router = APIRouter(prefix="/api", tags=["assets"])

    # === 録画済みアセット ===

    @router.get(
        "/assets/recorded",
        response_model=List[RecordedVideoItem],
    )
    async def get_recorded_assets() -> List[RecordedVideoItem]:
        """録画済みビデオ一覧を取得。"""
        try:
            dtos = await server.list_recorded_videos_uc.execute()
            # Application DTO → Interface DTO に変換
            return [
                RecordedVideoItem(
                    id=dto.video_id,
                    path=dto.path,
                    filename=dto.filename,
                    started_at=dto.started_at,
                    game_mode=dto.game_mode,
                    match=dto.match,
                    rule=dto.rule,
                    stage=dto.stage,
                    rate=dto.rate,
                    judgement=dto.judgement,
                    kill=dto.kill,
                    death=dto.death,
                    special=dto.special,
                    allies=list(dto.allies) if dto.allies else None,
                    enemies=list(dto.enemies) if dto.enemies else None,
                    hazard=dto.hazard,
                    golden_egg=dto.golden_egg,
                    power_egg=dto.power_egg,
                    rescue=dto.rescue,
                    rescued=dto.rescued,
                    has_subtitle=dto.has_subtitle,
                    has_thumbnail=dto.has_thumbnail,
                    duration_seconds=dto.duration_seconds,
                    size_bytes=dto.size_bytes,
                )
                for dto in dtos
            ]
        except Exception as e:
            server.logger.error(
                "録画一覧取得エラー", error=str(e), exc_info=True
            )
            raise

    @router.delete("/assets/recorded/{video_id:path}")
    async def delete_recorded_asset(video_id: str) -> JSONResponse:
        """録画済みビデオを削除。"""
        try:
            await server.delete_recorded_video_uc.execute(video_id)
            return JSONResponse(content={"status": "ok"})
        except FileNotFoundError as exc:
            # 存在しなくても契約上はエンドポイントが存在すればよい
            server.logger.warning(str(exc))
            return JSONResponse(
                status_code=status.HTTP_204_NO_CONTENT,
                content={"status": "not_found"},
            )

    @router.get("/videos/recorded/{video_id:path}")
    async def get_recorded_video(video_id: str) -> FileResponse:
        """録画済みビデオファイルを取得。

        video_id は base_dir からの相対パス（例: recorded/xxx.mp4）
        """
        video_path = Path(video_id)
        # 絶対パスでない場合は base_dir からの相対として解決
        if not video_path.is_absolute():
            video_path = server.base_dir / video_id

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

    @router.get("/thumbnails/recorded/{filename}")
    async def get_recorded_thumbnail(filename: str) -> FileResponse:
        """録画済みビデオのサムネイルを取得。"""
        # base_dir/recorded（録画ファイルの保存先）から解決
        thumbnail_path = server.base_dir / "recorded" / filename
        server.logger.debug(
            "サムネイル取得",
            filename=filename,
            base_dir=str(server.base_dir),
            thumbnail_path=str(thumbnail_path),
            exists=thumbnail_path.exists(),
        )
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

    # === 編集済みアセット ===

    @router.get(
        "/assets/edited",
        response_model=List[EditedVideoItem],
    )
    async def get_edited_assets() -> List[EditedVideoItem]:
        """編集済みビデオ一覧を取得。"""
        dtos = await server.list_edited_videos_uc.execute()
        # Application DTO → Interface DTO に変換
        return [
            EditedVideoItem(
                id=dto.video_id,
                path=dto.path,
                filename=dto.filename,
                duration_seconds=dto.duration_seconds,
                has_subtitle=dto.has_subtitle,
                has_thumbnail=dto.has_thumbnail,
                metadata=dto.metadata,
                updated_at=dto.updated_at,
                size_bytes=dto.size_bytes,
                title=dto.title,
                description=dto.description,
            )
            for dto in dtos
        ]

    @router.delete("/assets/edited/{video_id:path}")
    async def delete_edited_asset(video_id: str) -> JSONResponse:
        """編集済みビデオを削除。"""
        try:
            await server.delete_edited_video_uc.execute(video_id)
            return JSONResponse(content={"status": "ok"})
        except FileNotFoundError as exc:
            server.logger.warning(str(exc))
            return JSONResponse(
                status_code=status.HTTP_204_NO_CONTENT,
                content={"status": "not_found"},
            )

    @router.get("/videos/edited/{video_id:path}")
    async def get_edited_video(video_id: str) -> FileResponse:
        """編集済みビデオファイルを取得。

        video_id は base_dir からの相対パス（例: edited/xxx.mkv）
        """
        video_path = Path(video_id)
        # 絶対パスでない場合は base_dir からの相対として解決
        if not video_path.is_absolute():
            video_path = server.base_dir / video_id

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

    @router.get("/thumbnails/edited/{filename}")
    async def get_edited_thumbnail(filename: str) -> FileResponse:
        """編集済みビデオのサムネイルを取得。"""
        # base_dir/edited（編集ファイルの保存先）から解決
        thumbnail_path = server.base_dir / "edited" / filename
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

    # === 編集・アップロード処理 ===

    @router.post(
        "/process/edit-upload",
        response_model=EditUploadTriggerResponse,
    )
    async def trigger_edit_upload(
        auto: bool = Query(False, description="自動処理トリガーかどうか"),
    ) -> JSONResponse:
        """編集・アップロード処理を開始。"""
        try:
            if auto:
                await server.auto_process_service.start_auto_process()
            else:
                await server.start_edit_upload_uc.execute()
            # バックグラウンドタスクを開始したため、状態は"running"として返す
            # (実際のAutoEditorの状態更新は非同期タスク内で行われるため、
            #  このタイミングでは"idle"の可能性があるが、論理的には"running"が正しい)
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "accepted": True,
                    "message": "編集・アップロード処理を開始しました",
                    "status": {
                        "state": "running",
                        "started_at": None,
                        "finished_at": None,
                        "error": None,
                    },
                },
            )
        except RuntimeError as e:
            # 既に実行中の場合は現在の状態を返す
            status_dto = await server.get_edit_upload_status_uc.execute()
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "accepted": False,
                    "message": str(e),
                    "status": {
                        "state": status_dto.state,
                        "started_at": None,
                        "finished_at": None,
                        "error": None,
                    },
                },
            )

    @router.get(
        "/process/status",
        response_model=EditUploadStatus,
    )
    async def get_edit_upload_status() -> EditUploadStatus:
        """編集・アップロード処理の状態を取得。"""
        dto = await server.get_edit_upload_status_uc.execute()
        # Application DTO → Interface DTO に変換
        # Note: Application DTOのstateは文字列、Interface DTOはLiteral型
        # Note: 現在はstarted_at/finished_atは未実装のためNone
        return EditUploadStatus(
            state=dto.state,
        )

    return router


__all__ = ["create_assets_router"]
