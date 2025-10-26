"""pywebview based desktop application.

FastAPIバックエンドとpywebviewフロントエンドを統合したデスクトップアプリ。
"""

from __future__ import annotations

import multiprocessing
import sys
import time
import traceback
from pathlib import Path

import uvicorn
import webview
from structlog.stdlib import BoundLogger

from splat_replay.shared.logger import get_logger
from splat_replay.shared.paths import PROJECT_ROOT


def find_frontend_dist() -> Path:
    """フロントエンドdistディレクトリを検索。

    PyInstaller環境では sys._MEIPASS ベースから、
    通常環境ではプロジェクトルートから相対パスで検索。

    Returns:
        distディレクトリのパス

    Raises:
        FileNotFoundError: distディレクトリが見つからない場合
    """
    # PROJECT_ROOT は PyInstaller 環境にも対応済み
    dist = PROJECT_ROOT / "frontend" / "dist"

    if not dist.exists():
        raise FileNotFoundError(
            f"Frontend dist not found at {dist}. "
            "Run 'npm run build' in frontend directory first."
        )

    return dist


def start_backend_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """FastAPIバックエンドサーバーを起動。

    Args:
        host: バインドするホスト
        port: バインドするポート
    """
    import traceback

    logger = get_logger()

    try:
        logger.info("Starting FastAPI backend", host=host, port=port)

        # 遅延インポートでモジュールレベルの初期化を回避
        from splat_replay.web.app import app, app_runtime

        # Runtimeを起動
        app_runtime.start()

        # デバッグ用: ログをコンソールに出力
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="debug",  # infoからdebugに変更
            access_log=True,  # Falseからtrueに変更
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
    url: str, timeout: int = 30, interval: float = 0.5
) -> bool:
    """バックエンドサーバーの起動を待機。

    Args:
        url: バックエンドURL
        timeout: タイムアウト秒数
        interval: チェック間隔秒数

    Returns:
        起動成功ならTrue、タイムアウトならFalse
    """
    import httpx

    logger = get_logger()
    logger.info("Waiting for backend to start", url=url, timeout=timeout)

    elapsed = 0.0
    while elapsed < timeout:
        try:
            with httpx.Client() as client:
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
        title: str = "Splat Replay",
        width: int = 1200,
        height: int = 900,
        backend_host: str = "127.0.0.1",
        backend_port: int = 8000,
    ) -> None:
        """初期化。

        Args:
            title: ウィンドウタイトル
            width: ウィンドウ幅
            height: ウィンドウ高さ
            backend_host: バックエンドホスト
            backend_port: バックエンドポート
        """
        self.title = title
        self.width = width
        self.height = height
        self.backend_host = backend_host
        self.backend_port = backend_port
        self.backend_url = f"http://{backend_host}:{backend_port}"
        self.logger: BoundLogger = get_logger()

        # フロントエンドパスを検索
        try:
            self.frontend_dist = find_frontend_dist()
        except FileNotFoundError as e:
            self.logger.error(str(e))
            raise

    def run(self) -> None:
        """アプリケーションを起動。"""
        self.logger.info(
            "Starting Splat Replay WebView App",
            is_frozen=getattr(sys, "frozen", False),
            project_root=str(PROJECT_ROOT),
            frontend_dist=str(self.frontend_dist),
        )

        # バックエンドサーバーを別プロセスで起動
        backend_process = multiprocessing.Process(
            target=start_backend_server,
            args=(self.backend_host, self.backend_port),
            daemon=True,
        )
        backend_process.start()

        # バックエンドの起動を待機
        if not wait_for_backend(self.backend_url):
            self.logger.error("Failed to start backend server")
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


def main() -> None:
    """エントリーポイント。"""
    logger = get_logger()

    try:
        logger.info("=== Splat Replay WebView App Starting ===")
        logger.info(f"Python executable: {sys.executable}")
        logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")
        logger.info(f"PROJECT_ROOT: {PROJECT_ROOT}")

        # Windows multiprocessing対策
        if sys.platform == "win32":
            multiprocessing.freeze_support()

        app_instance = SplatReplayWebViewApp()
        app_instance.run()

    except Exception as e:
        logger.error("Fatal error occurred", error=str(e), exc_info=True)
        print(f"\n{'=' * 60}")
        print("FATAL ERROR:")
        print(f"{'=' * 60}")
        print(f"{type(e).__name__}: {e}")
        print(f"\n{'=' * 60}")
        print("Traceback:")
        print(f"{'=' * 60}")
        traceback.print_exc()
        print(f"{'=' * 60}\n")
        input("Press Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
