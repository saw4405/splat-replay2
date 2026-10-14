from __future__ import annotations

import os
import sys
from pathlib import Path


def _get_project_root() -> Path:
    """プロジェクトルートを取得（_internal内のリソース用）。

    macOS app では Contents/Resources、それ以外の frozen 環境では
    PyInstaller の sys._MEIPASS、通常環境では repo ルートを使用する。

    Note:
        frontend/distなど、_internalに配置されるリソース用。
    """
    # PyInstaller環境の検出
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            try:
                resources_dir = (
                    Path(sys.executable).parent.parent / "Resources"
                )
                if resources_dir.is_dir():
                    return resources_dir
            except Exception:
                pass
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        # フォールバック: 実行ファイルの親ディレクトリ
        try:
            return Path(sys.executable).resolve().parent
        except Exception:
            pass
    # 最終フォールバック: このファイルから上位6階層を使用
    # backend/src/splat_replay/infrastructure/filesystem/paths.py → repo root
    return Path(__file__).resolve().parents[5]


def _get_runtime_root() -> Path:
    """ランタイムルート（ユーザーデータ用）を取得。

    macOS frozen 環境では Application Support、Windows frozen 環境では
    実行ファイルのあるディレクトリ、
    通常環境では backend ルート（pyproject.toml のある位置）を使用。

    これはvideos/, config/, logs/ などユーザーデータが保存される
    ベースディレクトリとして使用される。
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return (
                Path.home()
                / "Library"
                / "Application Support"
                / "io.github.saw4405.splatreplay"
            )
        # PyInstaller環境: 実行ファイルのあるディレクトリ
        try:
            return Path(sys.executable).resolve().parent
        except Exception:
            pass
    # 通常環境: backend ルート
    return Path(__file__).resolve().parents[4]


def _is_macos_frozen() -> bool:
    return sys.platform == "darwin" and bool(getattr(sys, "frozen", False))


def _get_assets_dir() -> Path:
    # macOS bundle の assets は読み取り専用リソースとして同梱される。
    root = _get_project_root() if _is_macos_frozen() else _get_runtime_root()
    return root / "assets"


def _get_thumbnail_assets_dir() -> Path:
    if _is_macos_frozen():
        return _get_runtime_root() / "assets" / "thumbnail"
    return _get_assets_dir() / "thumbnail"


# バンドル内の静的リソース用ルート（frontend/dist 等）
PROJECT_ROOT = _get_project_root()

# ランタイムルート（ユーザーデータ用）
RUNTIME_ROOT = _get_runtime_root()
IS_MACOS_FROZEN = _is_macos_frozen()

# --- Top level directories ---
ASSETS_DIR = _get_assets_dir()

# ユーザーデータ（実行時に生成・変更されるファイル）
CONFIG_DIR = RUNTIME_ROOT / "config"
OUTPUTS_DIR = RUNTIME_ROOT / "outputs"
VIDEOS_DIR = RUNTIME_ROOT / "videos"  # 録画/編集済動画のベースディレクトリ
THUMBNAIL_ASSETS_DIR = _get_thumbnail_assets_dir()

# よく利用する設定ファイル/認証ファイル
SETTINGS_FILE = Path(
    os.getenv("SPLAT_REPLAY_SETTINGS_FILE", str(CONFIG_DIR / "settings.toml"))
)
IMAGE_MATCHING_FILE = CONFIG_DIR / "image_matching.yaml"


def asset(path: str) -> Path:
    """assets ディレクトリ以下のパスを返す。"""
    return ASSETS_DIR / path


def config(path: str) -> Path:
    """config ディレクトリ以下のパスを返す。"""
    return CONFIG_DIR / path


def thumbnail_asset(path: str) -> Path:
    """サムネイル用アセット (assets/thumbnail) 以下のパスを返す。"""
    return THUMBNAIL_ASSETS_DIR / path
