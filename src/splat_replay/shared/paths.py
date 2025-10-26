from __future__ import annotations

import sys
from pathlib import Path


def _get_project_root() -> Path:
    """プロジェクトルートを取得。

    PyInstaller環境では sys._MEIPASS をベースにし、
    通常環境では __file__ から相対的に解決する。
    """
    # PyInstaller環境の検出（堅牢化）
    # - sys.frozen が True で、sys._MEIPASS が設定されている場合は
    #   一時展開ディレクトリを候補とする。ただし、ビルド時に期待する
    #   リソース（config/ や assets/）が含まれていないケースもあるため、
    #   存在確認を行い、なければ実行ファイルの親フォルダへフォールバックする。
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cand = Path(meipass)
            # 簡易的な存在確認: config または assets ディレクトリがあるか
            if (cand / "config").exists() or (cand / "assets").exists():
                return cand
        # 上記がダメなら、実行ファイルの親ディレクトリをプロジェクトルート候補とする
        try:
            exe_parent = Path(sys.executable).resolve().parent
            return exe_parent
        except Exception:
            # どれも取得できない場合は次のフォールバックへ進む
            pass
    # 最終フォールバック: このファイルから上位4階層を使用
    # （通常環境と同じルールをここでも適用して型/静的解析エラーを避ける）
    return Path(__file__).resolve().parent.parent.parent.parent


def _get_runtime_root() -> Path:
    """ランタイムルート（ユーザーデータ用）を取得。

    PyInstaller環境では実行ファイルのあるディレクトリ、
    通常環境ではプロジェクトルートと同じ。

    これはvideos/, config/, logs/ などユーザーデータが保存される
    ベースディレクトリとして使用される。
    """
    if getattr(sys, "frozen", False):
        # PyInstaller環境: 実行ファイルのあるディレクトリ
        try:
            return Path(sys.executable).resolve().parent
        except Exception:
            pass
    # 通常環境: PROJECT_ROOT と同じ
    return _get_project_root()


# プロジェクトルート（静的リソース用）
PROJECT_ROOT = _get_project_root()

# ランタイムルート（ユーザーデータ用）
RUNTIME_ROOT = _get_runtime_root()

# --- Top level directories ---
# 静的リソース（PyInstallerでパッケージ化されたファイル）
ASSETS_DIR = PROJECT_ROOT / "assets"

# ユーザーデータ（実行時に生成・変更されるファイル）
CONFIG_DIR = RUNTIME_ROOT / "config"
VIDEOS_DIR = RUNTIME_ROOT / "videos"  # 録画/編集済動画のベースディレクトリ

# よく利用する設定ファイル/認証ファイル
SETTINGS_FILE = CONFIG_DIR / "settings.toml"
IMAGE_MATCHING_FILE = CONFIG_DIR / "image_matching.yaml"

# アセットサブディレクトリ
THUMBNAIL_ASSETS_DIR = ASSETS_DIR / "thumbnail"


def asset(path: str) -> Path:
    """assets ディレクトリ以下のパスを返す。"""
    return ASSETS_DIR / path


def config(path: str) -> Path:
    """config ディレクトリ以下のパスを返す。"""
    return CONFIG_DIR / path


def thumbnail_asset(path: str) -> Path:
    """サムネイル用アセット (assets/thumbnail) 以下のパスを返す。"""
    return THUMBNAIL_ASSETS_DIR / path
