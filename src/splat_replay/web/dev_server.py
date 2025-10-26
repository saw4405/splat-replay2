"""Development server launcher for frontend and backend."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def start_dev_server() -> None:
    """Start both frontend (Vite) and backend (FastAPI) servers."""
    frontend_dir = Path(__file__).parent.parent.parent.parent / "frontend"

    if not frontend_dir.exists():
        print(
            f"エラー: フロントエンドディレクトリが見つかりません: {frontend_dir}"
        )
        sys.exit(1)

    # Check if node_modules exists
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        print("依存関係をインストール中...")
        try:
            subprocess.run(
                ["npm.cmd", "install"]
                if os.name == "nt"
                else ["npm", "install"],
                cwd=frontend_dir,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"エラー: npm installに失敗しました: {e}")
            sys.exit(1)

    # Start frontend dev server
    print("フロントエンド開発サーバーを起動中...")
    try:
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        frontend_process = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=frontend_dir,
            shell=True,
        )
    except Exception as e:
        print(f"エラー: フロントエンドサーバーの起動に失敗しました: {e}")
        sys.exit(1)

    # Wait a bit for frontend to start
    time.sleep(2)

    # Start backend server using uvicorn directly
    print("バックエンドサーバーを起動中...")
    try:
        # Use Python module execution to avoid CLI container initialization
        # Note: --reload disabled to avoid Windows multiprocessing issues
        backend_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "splat_replay.web.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            shell=True,
        )
    except Exception as e:
        print(f"エラー: バックエンドサーバーの起動に失敗しました: {e}")
        frontend_process.terminate()
        sys.exit(1)

    print("\n" + "=" * 60)
    print("開発サーバーが起動しました!")
    print("=" * 60)
    print("フロントエンド: http://localhost:5173")
    print("バックエンド:     http://localhost:8000")
    print("API ドキュメント: http://localhost:8000/docs")
    print("=" * 60)
    print("終了するには Ctrl+C を押してください\n")

    try:
        # Wait for processes
        frontend_process.wait()
        backend_process.wait()
    except KeyboardInterrupt:
        print("\nサーバーを停止中...")
        frontend_process.terminate()
        backend_process.terminate()
        try:
            frontend_process.wait(timeout=5)
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            frontend_process.kill()
            backend_process.kill()
        print("サーバーが停止しました")


if __name__ == "__main__":
    start_dev_server()
