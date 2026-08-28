"""品質ゲートが使うリポジトリ内ランタイムディレクトリを準備する。"""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    """必要なランタイムディレクトリを作成する。"""
    repo_root = Path(__file__).resolve().parents[1]
    directories = (
        repo_root / ".tmp",
        repo_root / ".npm-cache",
        repo_root / ".pre-commit-cache",
        repo_root / ".pre-commit-cache" / "virtualenv-app-data",
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
