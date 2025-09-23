from pathlib import Path

# プロジェクトルート: このファイルから上位 4 階層 (src/splat_replay/shared/ -> ルート)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# --- Top level directories ---
ASSETS_DIR = PROJECT_ROOT / "assets"
CONFIG_DIR = PROJECT_ROOT / "config"
VIDEOS_DIR = PROJECT_ROOT / "videos"  # 録画/編集済動画のベースディレクトリ

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
