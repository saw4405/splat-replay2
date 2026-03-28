"""アセット（録画・編集済み動画）管理ルーター。

責務：
- 録画済み/編集済みビデオの一覧取得
- 録画済み/編集済みビデオの削除
- ビデオファイル・サムネイル画像の配信
- 編集・アップロード処理のトリガー/状態取得
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse

from splat_replay.application.dto.assets import EditUploadStatusDTO
from splat_replay.interface.web.converters import to_recorded_video_item
from splat_replay.interface.web.schemas import (
    EditedVideoItem,
    EditUploadProcessOptionsUpdateRequest,
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

    def _to_edit_upload_status(dto: EditUploadStatusDTO) -> EditUploadStatus:
        return EditUploadStatus(
            state=dto.state,
            started_at=None,
            finished_at=None,
            error=dto.message if dto.state == "failed" else None,
            sleep_after_upload_default=dto.sleep_after_upload_default,
            sleep_after_upload_effective=dto.sleep_after_upload_effective,
            sleep_after_upload_overridden=dto.sleep_after_upload_overridden,
        )

    # === 録画済みアセット ===

    @router.get(
        "/assets/recorded",
        response_model=List[RecordedVideoItem],
    )
    async def get_recorded_assets() -> List[RecordedVideoItem]:
        """録画済みビデオ一覧を取得。"""
        try:
            dtos = await server.list_recorded_videos_uc.execute()
            return [to_recorded_video_item(dto) for dto in dtos]
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

    # === 編集・アップロード ===

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
                server.auto_process_service.on_new_execution()
                await server.start_edit_upload_uc.execute()
            status_dto = await server.get_edit_upload_status_uc.execute()
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "accepted": True,
                    "message": "編集・アップロード処理を開始しました",
                    "status": _to_edit_upload_status(status_dto).dict(),
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
                    "status": _to_edit_upload_status(status_dto).dict(),
                },
            )

    @router.get(
        "/process/status",
        response_model=EditUploadStatus,
    )
    async def get_edit_upload_status() -> EditUploadStatus:
        """編集・アップロード処理の状態を取得。"""
        dto = await server.get_edit_upload_status_uc.execute()
        return _to_edit_upload_status(dto)

    @router.patch(
        "/process/edit-upload/options",
        response_model=EditUploadStatus,
    )
    async def update_edit_upload_process_options(
        request: EditUploadProcessOptionsUpdateRequest,
    ) -> EditUploadStatus:
        """編集中・アップロード中の一時オプションを更新する。"""
        try:
            server.start_edit_upload_uc.update_sleep_after_upload(
                request.sleep_after_upload
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        if not request.sleep_after_upload:
            server.auto_process_service.cancel_pending_sleep()
        else:
            server.auto_process_service.reactivate_sleep()

        dto = await server.get_edit_upload_status_uc.execute()
        return _to_edit_upload_status(dto)

    return router


def create_file_serving_router(server: WebAPIServer) -> APIRouter:
    """ファイル配信ルーターを作成（/apiプレフィックス無し）。

    Args:
        server: WebAPIServerインスタンス

    Returns:
        設定済みのAPIRouter
    """
    router = APIRouter(tags=["files"])

    # === 録画済みビデオファイル配信 ===

    @router.get("/videos/recorded/{video_id:path}")
    async def get_recorded_video(video_id: str) -> FileResponse:
        """録画済みビデオファイルを取得。

        video_id は base_dir からの相対パス（例: recorded/xxx.mp4）
        """
        try:
            # パストラバーサル対策: 絶対パスを解決しbase_dir配下にあるか確認
            video_path = (server.base_dir / video_id).resolve()
            base_resolved = server.base_dir.resolve()

            # base_dir配下にあるか確認
            if not str(video_path).startswith(str(base_resolved)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid path",
                )

            if not video_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video not found: {video_id}",
                )

            if not video_path.is_file():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Path is not a file",
                )
        except (ValueError, OSError) as exc:
            # パス解決エラー
            server.logger.warning(
                "不正なパスアクセス", video_id=video_id, error=str(exc)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid path",
            ) from exc
        except HTTPException:
            # HTTPExceptionは再送出
            raise

        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=video_path.name,
        )

    @router.get("/thumbnails/recorded/{filename}")
    async def get_recorded_thumbnail(filename: str) -> FileResponse:
        """録画済みビデオのサムネイルを取得。"""
        try:
            # パストラバーサル対策
            thumbnail_path = (
                server.base_dir / "recorded" / filename
            ).resolve()
            base_resolved = (server.base_dir / "recorded").resolve()

            if not str(thumbnail_path).startswith(str(base_resolved)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid path",
                )

            if not thumbnail_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Thumbnail not found: {filename}",
                )

            if not thumbnail_path.is_file():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Path is not a file",
                )
        except (ValueError, OSError) as exc:
            server.logger.warning(
                "不正なパスアクセス", filename=filename, error=str(exc)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid path",
            ) from exc

        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/png",
            filename=thumbnail_path.name,
        )

    # === 編集済みビデオファイル配信 ===

    @router.get("/videos/edited/{video_id:path}")
    async def get_edited_video(video_id: str) -> FileResponse:
        """編集済みビデオファイルを取得。

        video_id は base_dir からの相対パス（例: edited/xxx.mkv）
        """
        try:
            # パストラバーサル対策
            video_path = (server.base_dir / video_id).resolve()
            base_resolved = server.base_dir.resolve()

            if not str(video_path).startswith(str(base_resolved)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid path",
                )

            if not video_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video not found: {video_id}",
                )

            if not video_path.is_file():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Path is not a file",
                )
        except (ValueError, OSError) as exc:
            server.logger.warning(
                "不正なパスアクセス", video_id=video_id, error=str(exc)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid path",
            ) from exc

        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=video_path.name,
        )

    @router.get("/thumbnails/edited/{filename}")
    async def get_edited_thumbnail(filename: str) -> FileResponse:
        """編集済みビデオのサムネイルを取得。"""
        try:
            # パストラバーサル対策
            thumbnail_path = (server.base_dir / "edited" / filename).resolve()
            base_resolved = (server.base_dir / "edited").resolve()

            if not str(thumbnail_path).startswith(str(base_resolved)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid path",
                )

            if not thumbnail_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Thumbnail not found: {filename}",
                )

            if not thumbnail_path.is_file():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Path is not a file",
                )
        except (ValueError, OSError) as exc:
            server.logger.warning(
                "不正なパスアクセス", filename=filename, error=str(exc)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid path",
            ) from exc

        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/png",
            filename=thumbnail_path.name,
        )

    return router


__all__ = ["create_assets_router", "create_file_serving_router"]
