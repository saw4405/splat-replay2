"""pywebview based desktop application.

FastAPIバックエンドとpywebviewフロントエンドを統合したデスクトップアプリ。
"""

from __future__ import annotations

import multiprocessing
import sys
import time
import traceback
from pathlib import Path

import structlog
import uvicorn
import webview
from structlog.stdlib import BoundLogger


def find_frontend_dist(project_root: Path) -> Path:
    """フロントエンドdistディレクトリを検索。

    PyInstaller環境では sys._MEIPASS ベースから、
    通常環境ではプロジェクトルートから相対パスで検索。

    Args:
        project_root: プロジェクトルート

    Returns:
        distディレクトリのパス

    Raises:
        FileNotFoundError: distディレクトリが見つからない場合
    """
    # PROJECT_ROOT は PyInstaller 環境にも対応済み
    dist = project_root / "frontend" / "dist"

    if not dist.exists():
        raise FileNotFoundError(
            f"Frontend dist not found at {dist}. "
            "Run 'npm run build' in frontend directory first."
        )

    return dist


def start_backend_server(
    app_import_path: str, host: str = "127.0.0.1", port: int = 8000
) -> None:
    """FastAPIバックエンドサーバーを起動。

    Args:
        app_import_path: uvicorn で起動する ASGI アプリの import パス
        host: バインドするホスト
        port: バインドするポート
    """
    logger = structlog.get_logger()

    try:
        logger.info(
            "Starting FastAPI backend",
            host=host,
            port=port,
            app=app_import_path,
        )

        uvicorn.run(
            app_import_path,
            host=host,
            port=port,
            log_level="debug",  # infoからdebugに変更
            access_log=True,  # Falseからtrueに変更
            factory=True,
        )
    except Exception as e:
        logger.error("Backend server error", error=str(e), exc_info=True)
        print(f"\n{'=' * 60}")
        print("BACKEND SERVER ERROR:")
        print(f"{'=' * 60}")
        print(f"{type(e).__name__}: {e}")
        print(f"\n{'=' * 60}")
        print("Traceback:")
        print(f"{'=' * 60}")
        traceback.print_exc()
        print(f"{'=' * 60}\n")
        raise


def wait_for_backend(
    url: str,
    timeout: int = 120,
    interval: float = 0.5,
    logger: BoundLogger | None = None,
) -> bool:
    """バックエンドサーバーの起動を待機。

    Args:
        url: バックエンドURL
        timeout: タイムアウト秒数
        interval: チェック間隔秒数
        logger: 使用するロガー（未指定時はデフォルト）

    Returns:
        起動成功ならTrue、タイムアウトならFalse
    """
    import httpx

    if logger is None:
        logger = structlog.get_logger()
    logger.info("Waiting for backend to start", url=url, timeout=timeout)

    elapsed = 0.0
    while elapsed < timeout:
        try:
            # frozen モードでは SSL 証明書検証を無効化（ローカルホスト通信のため）
            with httpx.Client(verify=False) as client:
                response = client.get(f"{url}/api/health", timeout=2.0)
                if response.status_code == 200:
                    logger.info("Backend is ready", url=url)
                    return True
                else:
                    logger.warning(
                        "Backend health check failed",
                        status_code=response.status_code,
                    )
        except Exception as e:
            logger.debug(
                "Backend not ready yet", error=str(e), elapsed=elapsed
            )

        time.sleep(interval)
        elapsed += interval

    logger.error("Backend startup timeout", url=url, timeout=timeout)
    return False


class SplatReplayWebViewApp:
    """pywebviewベースのデスクトップアプリケーション。"""

    def __init__(
        self,
        *,
        project_root: Path,
        logger: BoundLogger,
        backend_app_module: str,
        title: str = "Splat Replay",
        width: int = 1200,
        height: int = 900,
        backend_host: str = "127.0.0.1",
        backend_port: int = 8000,
    ) -> None:
        """初期化。

        Args:
            project_root: プロジェクトルート
            logger: ロガー
            backend_app_module: 起動するバックエンド ASGI アプリの import パス
            title: ウィンドウタイトル
            width: ウィンドウ幅
            height: ウィンドウ高さ
            backend_host: バックエンドホスト
            backend_port: バックエンドポート
        """
        self.project_root = project_root
        self.logger = logger
        self.backend_app_module = backend_app_module
        self.title = title
        self.width = width
        self.height = height
        self.backend_host = backend_host
        self.backend_port = backend_port
        self.backend_url = f"http://{backend_host}:{backend_port}"

        # フロントエンドパスを検索
        try:
            self.frontend_dist = find_frontend_dist(self.project_root)
        except FileNotFoundError as e:
            self.logger.error(
                "フロントエンドディストリビューションが見つかりません",
                error=str(e),
            )
            raise

    def run(self) -> None:
        """アプリケーションを起動。"""
        self.logger.info(
            "Starting Splat Replay WebView App",
            is_frozen=getattr(sys, "frozen", False),
            project_root=str(self.project_root),
            frontend_dist=str(self.frontend_dist),
        )

        # バックエンドサーバーを別プロセスで起動
        backend_process = multiprocessing.Process(
            target=start_backend_server,
            args=(
                self.backend_app_module,
                self.backend_host,
                self.backend_port,
            ),
            daemon=True,
        )
        backend_process.start()

        # バックエンドの起動を待機
        if not wait_for_backend(self.backend_url, logger=self.logger):
            self.logger.error(
                "Failed to start backend server",
                error="Backend startup failed",
            )
            backend_process.terminate()
            sys.exit(1)

        # pywebviewウィンドウを作成
        try:
            # WebViewウィンドウ作成
            webview.create_window(
                title=self.title,
                url=self.backend_url,
                width=self.width,
                height=self.height,
                resizable=True,
                min_size=(400, 300),
                frameless=False,
                easy_drag=False,
            )

            # ウィンドウを起動
            # private_mode=Falseでカメラ許可などの設定を永続化
            webview.start(debug=False, private_mode=False)

        except Exception as e:
            self.logger.error("WebView error", error=str(e))
            raise
        finally:
            # クリーンアップ
            self.logger.info("Shutting down backend process")
            backend_process.terminate()
            backend_process.join(timeout=5)
            if backend_process.is_alive():
                backend_process.kill()


__all__ = ["SplatReplayWebViewApp"]
