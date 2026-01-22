"""通知API

Windows通知を送信するためのAPIエンドポイント。
pywebviewではブラウザのNotification APIが使えないため、
バックエンド経由でWindows通知を送信する。
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING or sys.platform == "win32":
    from winotify import Notification, audio


def create_notifications_router(
    assets_dir: Path,
) -> APIRouter:
    """通知ルーターを作成する。

    Args:
        assets_dir: アセットディレクトリ

    Returns:
        通知ルーター
    """
    router = APIRouter(prefix="/api/notifications", tags=["notifications"])

    # アイコンファイルのパスを事前に取得
    icon_path_png = assets_dir / "icon.png"
    icon_path_ico = assets_dir / "icon.ico"

    icon_path: Path | None = None
    if icon_path_png.exists():
        icon_path = icon_path_png
    elif icon_path_ico.exists():
        icon_path = icon_path_ico

    class NotificationRequest(BaseModel):
        """通知リクエスト"""

        title: str
        body: str
        icon: Literal["info", "success", "warning", "error"] = "info"

    @router.post("/send")
    async def send_notification(
        request: NotificationRequest,
    ) -> dict[str, str]:
        """Windows通知を送信する

        pywebview環境ではブラウザのNotification APIが使えないため、
        winotifyライブラリを使用してWindows通知を表示する。

        Args:
            request: 通知リクエスト

        Returns:
            結果メッセージ

        Raises:
            HTTPException: 通知の送信に失敗した場合
        """
        try:
            # Windowsの場合のみ通知を送信
            if sys.platform != "win32":
                return {
                    "status": "skipped",
                    "message": "Notifications only supported on Windows",
                }

            notification = Notification(
                app_id="Splat Replay",
                title=request.title,
                msg=request.body,
                duration="short",  # 短い時間表示
                icon=str(icon_path) if icon_path else "",
            )

            # 通知音を設定
            notification.set_audio(audio.Default, loop=False)

            # 通知を表示
            notification.show()

            return {"status": "success", "message": "Notification sent"}

        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"winotify library not installed: {str(e)}",
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send notification: {str(e)}",
            ) from e

    return router
